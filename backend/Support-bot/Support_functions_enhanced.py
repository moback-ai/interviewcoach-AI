import requests
import json
import os
from collections import defaultdict
import numpy as np
try:
    from sentence_transformers import SentenceTransformer
except Exception as sentence_transformer_import_error:
    SentenceTransformer = None
try:
    import faiss
except Exception as faiss_import_error:
    faiss = None
try:
    import ollama
except Exception as ollama_import_error:
    ollama = None

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get local backend API base from environment
BACKEND_API_BASE = os.getenv("BACKEND_API_BASE", "http://127.0.0.1:5000")

# -------------------------------
# Embedding Model + FAISS Globals
# -------------------------------
embedding_model = None
faq_index = None
faq_titles = []
faq_contents = []
faq_cache_key = None


def ollama_available():
    return ollama is not None


def retrieval_available():
    return SentenceTransformer is not None and faiss is not None


def get_embedding_model():
    global embedding_model
    if embedding_model is None:
        if SentenceTransformer is None:
            raise RuntimeError(
                f"sentence-transformers is unavailable: {sentence_transformer_import_error}"
            )
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return embedding_model

# -------------------------------
# FAQ Parsing (unchanged)
# -------------------------------
def load_faq_sections(faq_path="support_bot.md"):
    """Parse the FAQ markdown file into a dictionary of {title: content}."""
    sections = defaultdict(str)
    current_title = None

    with open(faq_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("## "):
                current_title = line.strip("# \n")
                sections[current_title] = ""
            elif current_title:
                sections[current_title] += line

    return dict(sections)

# -------------------------------
# Build FAISS Index (unchanged)
# -------------------------------
def build_faq_index(faq_sections):
    """Build FAISS index from FAQ sections."""
    global faq_index, faq_titles, faq_contents, faq_cache_key
    if not retrieval_available():
        faq_index = None
        faq_titles = list(faq_sections.keys())
        faq_contents = list(faq_sections.values())
        faq_cache_key = tuple(faq_titles)
        return

    cache_key = tuple(faq_sections.keys())
    if faq_index is not None and faq_cache_key == cache_key:
        return

    faq_titles = list(faq_sections.keys())
    faq_contents = list(faq_sections.values())
    faq_cache_key = cache_key

    corpus_embeddings = get_embedding_model().encode(
        [title + " " + content for title, content in faq_sections.items()],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    dim = corpus_embeddings.shape[1]
    faq_index = faiss.IndexFlatIP(dim)
    faq_index.add(corpus_embeddings)

# -------------------------------
# Retriever (unchanged)
# -------------------------------
def find_relevant_sections(query, top_k=2):
    """Retrieve most relevant FAQ sections using embeddings + FAISS."""
    if faq_index is None:
        if not faq_titles or not faq_contents:
            raise ValueError("FAQ index not built. Call build_faq_index first.")
        query_lower = query.lower()
        scored = []
        for title, content in zip(faq_titles, faq_contents):
            haystack = f"{title}\n{content}".lower()
            score = sum(1 for token in query_lower.split() if token and token in haystack)
            scored.append((score, title, content))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [(title, content) for _, title, content in scored[:top_k] if title]

    query_embedding = get_embedding_model().encode([query], convert_to_numpy=True, normalize_embeddings=True)
    distances, indices = faq_index.search(query_embedding, top_k)

    results = []
    for idx in indices[0]:
        if 0 <= idx < len(faq_titles):
            results.append((faq_titles[idx], faq_contents[idx]))
    return results

# -------------------------------
# LLM-Based Database Query Classifier
# -------------------------------
def needs_db_context(user_input, model="llama3"):
    """
    Use LLM to classify if the user query requires database context.
    Returns True if database query is needed, False otherwise.
    """
    system_prompt = """
    You are a classifier for a support bot.
    Task: Decide if the user query requires retrieving user-specific data from the database.
    Respond with ONLY 'yes' or 'no'.
    
    'yes' examples:
    - "What is my latest payment?"
    - "How many payments have I made?"
    - "Show me my last interview result."
    - "What email is linked to my account?"
    - "When did I last upload a resume?"
    - "How many interviews have I completed?"
    - "What was my last interview score?"
    - "Show me my payment history"
    - "Tell me about my recent interviews"
    - "What's my account status?"
    - "How much have I spent?"
    - "What jobs have I applied for?"
    - "What's my name?"
    - "What is my name?"
    - "Tell me my name"
    - "Who am I?"
    - "What's my full name?"
    - "What is my full name?"
    - "Show me my profile"
    - "What's in my profile?"
    - "Tell me about my account"
    - "What's my email?"
    - "What is my email address?"
    - "What's the email?"
    - "What is the email?"
    - "Tell me my email"
    - "Show me my email"
    - "What email do I use?"
    - "What email address do I have?"
    - "What's my account email?"
    - "What is my account email?"

    'no' examples:
    - "How do I upload my resume?"
    - "How do I make a payment?"
    - "What is AI Interview Coach?"
    - "How do I start an interview?"
    - "What features do you offer?"
    - "How do I create an account?"
    - "What are your pricing plans?"
    - "How do I contact support?"
    - "What is the interview process?"
    - "How do I reset my password?"
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_input}
    ]
    if not ollama_available():
        keywords = (
            "my ", "me ", "account", "payment", "payments", "interview", "profile",
            "resume", "email", "name", "spent", "history", "latest", "recent"
        )
        return any(keyword in user_input.lower() for keyword in keywords)
    
    try:
        response = ollama.chat(model=model, messages=messages)
        result = response["message"]["content"].strip().lower()
        return result == "yes"
    except Exception as e:
        print(f"[WARNING] LLM classifier failed: {e}, defaulting to False")
        return False

# -------------------------------
# Edge Function Caller
# -------------------------------
def call_backend_user_context(auth_token, backend_api_base=None):
    """
    Fetch user context from the local backend API.
    Returns formatted user context string or error message.
    """
    if backend_api_base is None:
        backend_api_base = BACKEND_API_BASE
    
    try:
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{backend_api_base}/api/support-bot-data",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return format_user_context(data.get('data')), None
            else:
                return None, f"API Error: {data.get('message', 'Unknown error')}"
        else:
            return None, f"HTTP {response.status_code}: {response.text}"
            
    except requests.exceptions.RequestException as e:
        return None, f"Request failed: {str(e)}"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON response: {str(e)}"

# -------------------------------
# Format User Context for LLM
# -------------------------------
def format_user_context(user_data):
    """
    Format user data into a clean context string for the LLM.
    """
    if not user_data:
        return "No user data available."
    
    context_parts = []
    
    # User Info
    user_info = user_data.get('user_info', {})
    context_parts.append(f"USER PROFILE:")
    context_parts.append(f"- Name: {user_info.get('full_name', 'Not provided')}")
    context_parts.append(f"- Email: {user_info.get('email', 'Not provided')}")
    context_parts.append(f"- Plan: {user_info.get('plan', 'basic')}")
    context_parts.append(f"- Account created: {user_info.get('created_at', 'Unknown')}")
    
    # Recent Payments
    payments = user_data.get('payments', [])
    if payments:
        context_parts.append(f"\nPAYMENT HISTORY ({len(payments)} payments):")
        for payment in payments[:5]:  # Show last 5 payments
            date = payment['paid_at'][:10] if payment['paid_at'] else 'Unknown date'
            context_parts.append(f"- ₹{payment['amount'] / 100:.2f} on {date} (Status: {payment['payment_status']})")
        if len(payments) > 5:
            context_parts.append(f"- ... and {len(payments) - 5} more payments")
    else:
        context_parts.append(f"\nPAYMENT HISTORY: No payments found")
    
    # Recent Interviews
    interviews = user_data.get('interviews', [])
    if interviews:
        context_parts.append(f"\nINTERVIEW HISTORY ({len(interviews)} interviews):")
        for interview in interviews[:5]:  # Show last 5 interviews
            date = interview['created_at'][:10] if interview['created_at'] else 'Unknown date'
            context_parts.append(f"- {interview['job_title']} on {date} (Status: {interview['status']}, Attempt: {interview['attempt_number']})")
        if len(interviews) > 5:
            context_parts.append(f"- ... and {len(interviews) - 5} more interviews")
    else:
        context_parts.append(f"\nINTERVIEW HISTORY: No interviews found")
    
    # Resumes
    resumes = user_data.get('resumes', [])
    if resumes:
        context_parts.append(f"\nUPLOADED RESUMES ({len(resumes)} resumes):")
        for resume in resumes[:3]:  # Show last 3 resumes
            date = resume['uploaded_at'][:10] if resume['uploaded_at'] else 'Unknown date'
            context_parts.append(f"- {resume['file_name']} (uploaded {date})")
    else:
        context_parts.append(f"\nUPLOADED RESUMES: No resumes found")
    
    # Job Descriptions
    job_descriptions = user_data.get('job_descriptions', [])
    if job_descriptions:
        context_parts.append(f"\nJOB APPLICATIONS ({len(job_descriptions)} jobs):")
        for jd in job_descriptions[:3]:  # Show last 3 job descriptions
            date = jd['created_at'][:10] if jd['created_at'] else 'Unknown date'
            context_parts.append(f"- {jd['title']} (applied {date})")
    else:
        context_parts.append(f"\nJOB APPLICATIONS: No job applications found")
    
    # Interview Feedback
    feedback = user_data.get('interview_feedback', [])
    if feedback:
        context_parts.append(f"\nINTERVIEW FEEDBACK: {len(feedback)} feedback entries available")
    
    return "\n".join(context_parts)

# -------------------------------
# Enhanced Generate Reply with LLM Classifier
# -------------------------------
def generate_support_reply(faq_sections, conversation_history, user_input, model="llama3", auth_token=None, backend_api_base=None):
    """
    Generate a contextual support reply using LLM-based classification and optional user data.
    """
    if backend_api_base is None:
        backend_api_base = BACKEND_API_BASE
    
    # Step 1: Classify if database context is needed
    needs_db = needs_db_context(user_input, model)
    user_context = ""
    
    print(f"[INFO] Query classification: {'DB context needed' if needs_db else 'FAQ only'}")
    print(f"[DEBUG] User input: '{user_input}'")
    print(f"[DEBUG] Auth token available: {bool(auth_token)}")
    print(f"[DEBUG] Using backend API base: {backend_api_base}")
    
    # Step 2: Fetch user data if needed and auth token is available
    if needs_db and auth_token:
        print(f"[INFO] Fetching user data from backend API...")
        user_context, error = call_backend_user_context(auth_token, backend_api_base)
        
        if user_context:
            print(f"[INFO] User data retrieved successfully")
            print(f"[DEBUG] User context preview: {user_context[:200]}...")
        else:
            print(f"[WARNING] Failed to fetch user data: {error}")
            user_context = "Unable to retrieve your personal data at the moment. Please try again later."
    elif needs_db and not auth_token:
        print(f"[INFO] Database context needed but no auth token provided")
        user_context = "To answer questions about your account, payments, or interviews, please sign in first."
    else:
        print(f"[INFO] No database context needed for this query")
    
    # Step 3: Retrieve relevant FAQ sections
    relevant_sections = find_relevant_sections(user_input, top_k=2)
    
    if relevant_sections:
        faq_context = "\n\n".join([f"### {title}\n{content}" for title, content in relevant_sections])
    else:
        faq_context = "No relevant FAQ section found."
    
    # Step 4: Build system prompt with appropriate context
    if user_context:
        system_prompt = f"""
        You are a helpful support assistant for the AI Interview Coach platform.
        
        ### User Context (Personal Data):
        {user_context}
        
        ### FAQ Knowledge Base:
        {faq_context}
        
        Instructions:
        - If the user asks about their personal data (payments, interviews, profile, etc.), use ONLY the User Context above.
        - For general questions about the platform, use the FAQ Knowledge Base.
        - Be concise and helpful (3–5 bullet points or steps max).
        - If you can't find the answer in either context, politely say so and suggest contacting support.
        - Be friendly and professional in your responses.
        """
    else:
        system_prompt = f"""
        You are a helpful support assistant for the AI Interview Coach platform.
        
        ### FAQ Knowledge Base:
        {faq_context}
        
        Instructions:
        - If the user message is just a greeting or small talk (e.g., "hi", "hello", "hey", "good morning"),
          reply briefly and warmly (1–2 sentences max), e.g. "Hi there 👋 How can I help you today?".
        - If the user asks about their personal data (payments, interviews, profile, etc.), use ONLY the User Context above.
        - For general platform questions, use the FAQ Knowledge Base.
        - Keep answers concise: no more than 3–5 bullet points or steps when needed.
        - If no relevant info exists, politely say so and suggest contacting support.
        - Always be friendly and professional.
        """

    messages = [{"role": "system", "content": system_prompt}] + conversation_history
    messages.append({"role": "user", "content": user_input})

    if not ollama_available():
        if user_context:
            return user_context, [title for title, _ in relevant_sections]
        if relevant_sections:
            title, content = relevant_sections[0]
            compact = " ".join(content.split())
            return f"{title}: {compact[:400]}".strip(), [title for title, _ in relevant_sections]
        return "Hello! How can I help you today?", []

    try:
        response = ollama.chat(model=model, messages=messages)
        return response["message"]["content"].strip(), [title for title, _ in relevant_sections]
    except Exception as e:
        print(f"[ERROR] generate_support_reply failed: {e}")
        return "Sorry, I encountered an error. Please try again.", []
