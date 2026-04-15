import os
import time
import uuid

from dotenv import load_dotenv

from Support_functions_enhanced import load_faq_sections, build_faq_index, generate_support_reply

load_dotenv()

BACKEND_API_BASE = os.getenv("BACKEND_API_BASE", "http://127.0.0.1:5000")


class SupportBotManager:
    def __init__(self, model="llama3", faq_path="support_bot.md", backend_api_base=None):
        self.model = model
        self.session_id = str(uuid.uuid4())
        self.conversation_history = []
        self.api_call_count = 0
        self.start_time = time.time()
        self.auth_token = None
        self.backend_api_base = backend_api_base or BACKEND_API_BASE

        self.faq_sections = load_faq_sections(faq_path)
        build_faq_index(self.faq_sections)

        greeting = "Hello! I'm your support assistant. How can I help you today?"
        self.conversation_history.append({"role": "assistant", "content": greeting})

    def set_auth_token(self, auth_token):
        self.auth_token = auth_token
        print(f"[INFO] Auth token set for session {self.session_id}")

    def receive_input(self, user_input: str):
        self.api_call_count += 1
        print(f"[INFO] API call #{self.api_call_count} | Session: {self.session_id}")

        self.conversation_history.append({"role": "user", "content": user_input})

        reply, retrieved_titles = generate_support_reply(
            self.faq_sections,
            self.conversation_history,
            user_input,
            model=self.model,
            auth_token=self.auth_token,
            backend_api_base=self.backend_api_base,
        )

        self.conversation_history.append({"role": "assistant", "content": reply})

        return {
            "session_id": self.session_id,
            "message": reply,
            "conversation_length": len(self.conversation_history),
            "retrieved_sections": retrieved_titles,
            "has_auth": self.auth_token is not None,
        }
