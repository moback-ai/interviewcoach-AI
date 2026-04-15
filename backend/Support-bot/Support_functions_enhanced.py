import ollama
import requests
import json
import os
from collections import defaultdict
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get Supabase URL from environment
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321")

# -------------------------------
# Embedding Model + FAISS Globals
# -------------------------------
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
faq_index = None
faq_titles = []
faq_contents = []

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
    global faq_index, faq_titles, faq_contents

    faq_titles = list(faq_sections.keys())
    faq_contents = list(faq_sections.values())

    corpus_embeddings = embedding_model.encode(
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
        raise ValueError("FAQ index not built. Call build_faq_index first.")

    query_embedding = embedding_model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
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
def call_edge_function(auth_token, supabase_url=None):
    """
    Call the support-bot-data edge function to fetch user context.
    Returns formatted user context string or error message.
    """
    # Use environment variable if no URL provided
    if supabase_url is None:
        supabase_url = SUPABASE_URL
    
    try:
        headers = {
            'Authorization': auth_token,
            'Content-Type': 'application/json'
        }
        
        response = requests.get(
            f"{supabase_url}/functions/v1/support-bot-data",
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
def generate_support_reply(faq_sections, conversation_history, user_input, model="llama3", auth_token=None, supabase_url=None):
    """
    Generate a contextual support reply using LLM-based classification and optional user data.
    """
    # Use environment variable if no URL provided
    if supabase_url is None:
        supabase_url = SUPABASE_URL
    
    # Step 1: Classify if database context is needed
    needs_db = needs_db_context(user_input, model)
    user_context = ""
    
    print(f"[INFO] Query classification: {'DB context needed' if needs_db else 'FAQ only'}")
    print(f"[DEBUG] User input: '{user_input}'")
    print(f"[DEBUG] Auth token available: {bool(auth_token)}")
    print(f"[DEBUG] Using Supabase URL: {supabase_url}")
    
    # Step 2: Fetch user data if needed and auth token is available
    if needs_db and auth_token:
        print(f"[INFO] Fetching user data from edge function...")
        user_context, error = call_edge_function(auth_token, supabase_url)
        
        if user_context:
            print(f"[INFO] User data retrieved successfully")
            print(f"[DEBUG] User context preview: {user_context[:200]}...")
        else:
            print(f"[WARNING] Failed to fetch user data: {error}")
            user_context = "Unable to retrieve your personal data at the moment. Please try again later."
    elif needs_db and not auth_token:
        print(f"[INFO] Database context needed but no auth token provided")
        user_context = "To answer questions about your account, payments, or interviews, please provide authentication."
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

    try:
        response = ollama.chat(model=model, messages=messages)
        return response["message"]["content"].strip(), [title for title, _ in relevant_sections]
    except Exception as e:
        print(f"[ERROR] generate_support_reply failed: {e}")
        return "Sorry, I encountered an error. Please try again.", []
