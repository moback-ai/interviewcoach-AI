import uuid
import time
import os
from Support_functions_enhanced import load_faq_sections, build_faq_index, generate_support_reply

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Get Supabase URL from environment
SUPABASE_URL = os.getenv("SUPABASE_URL", "http://localhost:54321")

class SupportBotManager:
    def __init__(self, model="llama3", faq_path="support_bot.md", supabase_url=None):
        self.model = model
        self.session_id = str(uuid.uuid4())
        self.conversation_history = []
        self.api_call_count = 0
        self.start_time = time.time()
        self.auth_token = None  # Will be set when user provides auth token
        
        # Use environment variable if no URL provided
        self.supabase_url = supabase_url or SUPABASE_URL
        
        # Load FAQ sections
        self.faq_sections = load_faq_sections(faq_path)
        
        # Build FAISS index for semantic retrieval
        build_faq_index(self.faq_sections)
        
        greeting = "Hello! I'm your support assistant. How can I help you today?"
        self.conversation_history.append({"role": "assistant", "content": greeting})

    def set_auth_token(self, auth_token):
        """Set the authentication token for database queries."""
        self.auth_token = auth_token
        print(f"[INFO] Auth token set for session {self.session_id}")

    def receive_input(self, user_input: str):
        """Process input and return support reply with LLM-based database classification."""
        self.api_call_count += 1
        print(f"[INFO] API call #{self.api_call_count} | Session: {self.session_id}")

        # Store user input
        self.conversation_history.append({"role": "user", "content": user_input})

        # Get reply using enhanced LLM-based classification
        reply, retrieved_titles = generate_support_reply(
            self.faq_sections,
            self.conversation_history,
            user_input,
            model=self.model,
            auth_token=self.auth_token,
            supabase_url=self.supabase_url
        )

        # Save reply
        self.conversation_history.append({"role": "assistant", "content": reply})

        return {
            "session_id": self.session_id,
            "message": reply,
            "conversation_length": len(self.conversation_history),
            "retrieved_sections": retrieved_titles,
            "has_auth": self.auth_token is not None
        }
