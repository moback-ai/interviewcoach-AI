import json
import os
import random
import re
import time
from difflib import SequenceMatcher

from Interview_functions import (
    log,
    assess_intro_progress,
    generate_contextual_intro_reply,
    generate_icebreaker_question,
    assess_icebreaker_response,
    assess_followup_response,
    generate_dynamic_question,
    evaluate_resume_response,
    generate_followup_question,
    evaluate_custom_response,
    generate_custom_followup,
    generate_model_answer,
    run_candidate_qna_turn,
    sanitize_interviewer_display_text,
    # ✅ REMOVED: generate_key_strengths_and_improvements - no longer needed
)


class InterviewManager:
    @classmethod
    def from_config(cls, config, model="llama3"):
        """Build manager without writing a temp JSON file (faster per /generate-response)."""
        instance = cls.__new__(cls)
        instance._init_new_session(model, config)
        return instance

    def __init__(self, model="llama3", config_path="interview_config.json"):
        with open(config_path, "r") as f:
            config = json.load(f)
        self._init_new_session(model, config)

    def _init_new_session(self, model, config):
        self.model = model
        self.api_call_count = 0
        self.stage = "introduction"
        self.conversation_history = []

        self.job_title = config.get("job_title", "this role")
        self.job_description = config.get("job_description", "")
        self.interview_style = config.get("interview_style", "conversational")
        self.interviewer_name = (config.get("interviewer_name") or "Sadhan").strip() or "Sadhan"
        self.required_questions = config.get("custom_questions", [])
        self.core_questions = config.get("core_questions", [])
        self.coding_requirement = config.get("coding_requirement", "")
        self.icebreakers = config.get("icebreakers", [])

# ========= Interview Time Limit ==================
        self.start_time = None
        limit_minutes = config.get("time_limit_minutes") or 0
        self.time_limit_seconds = int(limit_minutes) * 60 if limit_minutes > 0 else 0


# ========= Stage Flags ==================

        # === Intro Flags ===
        self.intro_done = False
        self.intro_retry_count = 0
        self.max_intro_retries = 3

        # === Ice breaker Flags ===
        self.current_icebreaker = ""
        self.icebreaker_question_asked = False
        self.icebreaker_done = False
        self.icebreaker_retry_count = 0
        self.max_icebreaker_retries = 3

        # === Intro Follow-up Flags ===
        self.current_followup_question = ""
        self.followup_retry_count = 0
        self.max_followup_retries = 3
        self.intro_followup_done = False

        # Resume Q&A
        self.resume_stage_done = False
        self.core_questions = config.get("core_questions", [])  # already exists
        self.current_resume_question_obj = None
        self.current_resume_question = ""
        self.current_coding_requirement = config.get("coding_requirement", "")
        self.asked_question_texts = []
        self.last_resume_response = ""
        self.resume_followup_retry_count = 0
        self.max_resume_followup_retries = 3

        # Custom Questions (disabled for now — resume goes straight to candidate Q&A)
        self.custom_qna_done = True
        self.required_questions = config.get("custom_questions", [])
        self.current_custom_question = ""
        self.last_custom_response = ""
        self.custom_followup_retry_count = 0
        self.max_custom_followup_retries = 3
        self.custom_followup_evaluations = []

        # Candidate questions - end of interview
        self.candidate_qna_done = False
        self.candidate_question_count = 0
        self.max_candidate_questions = 4  # Soft limit
        self.awaiting_manual_end = False

        # Candidate evaluation
        self.evaluation_log = []


        # === Initial greeting ===
        greeting = f"Welcome to the interview for the role of {self.job_title}. Let’s get started!"
        print(f"\n {greeting}\n")
        self.conversation_history.append({"role": "assistant", "content": greeting})

    def _question_key(self, text):
        cleaned = re.sub(r"[^a-z0-9]+", " ", (text or "").strip().lower())
        return " ".join(cleaned.split())

    def _ensure_runtime_state(self):
        if not hasattr(self, "asked_question_texts") or not isinstance(self.asked_question_texts, list):
            self.asked_question_texts = []
        if not hasattr(self, "current_resume_question_obj"):
            self.current_resume_question_obj = None
        if self.core_questions is None:
            self.core_questions = []
        if not hasattr(self, "awaiting_manual_end"):
            self.awaiting_manual_end = False

    def _has_asked_question(self, text):
        key = self._question_key(text)
        if not key:
            return False
        if key in self.asked_question_texts:
            return True
        return any(self._questions_are_similar(key, asked_key) for asked_key in self.asked_question_texts)

    def _mark_question_asked(self, text):
        key = self._question_key(text)
        if key and key not in self.asked_question_texts:
            self.asked_question_texts.append(key)

    def _questions_are_similar(self, first, second):
        first_key = self._question_key(first)
        second_key = self._question_key(second)
        if not first_key or not second_key:
            return False
        if first_key == second_key:
            return True
        first_words = set(first_key.split())
        second_words = set(second_key.split())
        if len(first_words) >= 5 and len(second_words) >= 5:
            overlap = len(first_words & second_words) / max(len(first_words | second_words), 1)
            if overlap >= 0.72:
                return True
        return SequenceMatcher(None, first_key, second_key).ratio() >= 0.82

    def _is_resume_followup_repeated(self, text):
        return (
            not (text or "").strip()
            or self._questions_are_similar(text, self.current_resume_question)
            or self._has_asked_question(text)
        )

    def _pop_next_resume_question(self):
        self._ensure_runtime_state()

        while self.core_questions:
            self.current_resume_question_obj = self.core_questions.pop(0)
            if isinstance(self.current_resume_question_obj, dict):
                question_text = self.current_resume_question_obj.get('question_text', '')
                requires_code = bool(self.current_resume_question_obj.get('requires_code', False))
            else:
                question_text = self.current_resume_question_obj
                requires_code = False

            if not question_text or self._has_asked_question(question_text):
                continue

            self.current_resume_question = question_text
            self.current_coding_requirement = requires_code
            self._mark_question_asked(question_text)
            return True

        self.current_resume_question_obj = None
        self.current_resume_question = ""
        self.current_coding_requirement = False
        return False

    def _emit_stream_text(self, on_token, text, chunk_size=24):
        if not on_token or not text:
            return
        clean = sanitize_interviewer_display_text(text)
        for i in range(0, len(clean), chunk_size):
            on_token(clean[i:i + chunk_size])

    def _build_resume_followup(self, user_input, on_token=None):
        followup = generate_followup_question(
            self.current_resume_question,
            user_input,
            on_token=on_token,
        )
        if self._is_resume_followup_repeated(followup):
            for candidate in [
                "Could you add one concrete example from your experience?",
                "What was your specific role in that work, and what outcome did it create?",
                "What was the main challenge in that situation, and how did you handle it?",
            ]:
                if not self._is_resume_followup_repeated(candidate):
                    followup = candidate
                    break
            else:
                followup = "Thanks, let's keep going."
        self._mark_question_asked(followup)
        return followup

    def is_time_exceeded(self):
        if self.time_limit_seconds <= 0:
            return False
        elapsed = getattr(self, "tracked_active_seconds", 0) or 0
        return elapsed >= self.time_limit_seconds


    def receive_input(self, user_input: str, on_token=None):
        self._ensure_runtime_state()
        self.api_call_count += 1
        print(f"[INFO] API call #{self.api_call_count} | Stage: {self.stage}")
        
        if self.start_time is None:
            self.start_time = time.time()
            print("[DEBUG] Interview timer started.")

        # ✅ NEW: Handle manual interview end command
        if user_input.strip().upper() == "END_INTERVIEW":
            print("[INFO] Manual interview end requested by user")
            self.awaiting_manual_end = False
            self.stage = "wrapup_evaluation"
            return {
                "stage": "manual_end",
                "message": "Thank you for completing the interview. Let me provide you with a comprehensive evaluation.",
                "awaiting_manual_end": False,
                **self.handle_wrapup_evaluation()  # ✅ This already includes "interview_done": True
            }

        # After candidate Q&A, lock further answers until End Interview is pressed.
        if getattr(self, "awaiting_manual_end", False):
            return {
                "stage": "wrapup_evaluation",
                "message": (
                    "We've finished the interview questions. "
                    "Please press the End Interview button for your feedback."
                ),
                "interview_done": False,
                "awaiting_manual_end": True,
            }

        # Check time limit
        if self.is_time_exceeded():
            print("[DEBUG] Time limit reached. Returning timeout flag.")
            return {
                "stage": "timeout",
                "message": "We've reached the time limit for this interview.",
                "timeout_detected": True  # ✅ Flag for frontend to handle
            }

        if not self.intro_done:
            return self.handle_intro_stage(user_input, on_token=on_token)

        if not self.icebreaker_done:
            return self.handle_icebreaker_stage(user_input, on_token=on_token)

        if not self.intro_followup_done:
            return self.handle_intro_followup_stage(user_input, on_token=on_token)
        if self.stage == "resume_discussion":
            return self.handle_resume_discussion_stage(user_input, on_token=on_token)
        if self.stage == "custom_questions":
            # Legacy/compat: immediately skip into candidate Q&A.
            return self._begin_candidate_questions_stage(on_token=on_token)
        if self.stage == "candidate_questions":
            return self.handle_candidate_questions_stage(user_input, on_token=on_token)
        if self.stage == "wrapup_evaluation" or getattr(self, "awaiting_manual_end", False):
            return {
                "stage": "wrapup_evaluation",
                "message": (
                    "Please press the End Interview button to end the interview and get your feedback."
                ),
                "interview_done": False,
                "awaiting_manual_end": True,
            }
        return {
            "stage": "done",
            "message": "All stages complete. Please press the END Interview Button to end the interview.",
            "interview_done": False,  # ✅ So your app can differentiate
            "awaiting_manual_end": True,
        }

    def _begin_candidate_questions_stage(self, on_token=None, preface=""):
        """Skip custom questions and open the candidate Q&A wrap-up prompt."""
        self.custom_qna_done = True
        self.stage = "candidate_questions"
        self.awaiting_manual_end = False
        prompt = (
            "I think we’ve reached the end of this interview. "
            "Do you have any questions for me before we wrap up?"
        )
        message = f"{preface}\n\n{prompt}".strip() if preface else prompt
        self.conversation_history.append({"role": "assistant", "content": message})
        return {
            "stage": "candidate_questions",
            "message": message,
            "awaiting_manual_end": False,
        }

    def _prompt_manual_end(self, message):
        """Lock further Q&A until the user presses End Interview."""
        self.candidate_qna_done = True
        self.awaiting_manual_end = True
        self.stage = "wrapup_evaluation"
        self.conversation_history.append({"role": "assistant", "content": message})
        return {
            "stage": "wrapup_evaluation",
            "message": message,
            "interview_done": False,
            "awaiting_manual_end": True,
        }


# ===== BEGINING OF - INTRO STAGE  =====

    def handle_intro_stage(self, user_input, on_token=None):
        from Interview_functions import log
        log("handle_intro_stage")

        self.conversation_history.append({"role": "user", "content": user_input})

        result = generate_contextual_intro_reply(
            self.job_title,
            self.job_description,
            self.conversation_history,
            user_input,
        )
        reply = result["message"]
        self.conversation_history.append({"role": "assistant", "content": reply})

        intro_status = assess_intro_progress(self.conversation_history)
        print(f"[DEBUG] assess_intro_progress → {intro_status}")

        if intro_status == "continue":
            self.intro_done = True
            self.stage = "icebreaker"

            # Immediately ask the icebreaker
            question = generate_icebreaker_question(
                self.job_title,
                conversation_history=self.conversation_history,
                on_token=on_token,
            )
            self.current_icebreaker = question
            self.icebreaker_question_asked = True
            self.conversation_history.append({"role": "assistant", "content": question})

            return {
                "stage": "icebreaker",
                "message": question
            }


        self.intro_retry_count += 1
        print(f"[DEBUG] Intro retry: {self.intro_retry_count}/{self.max_intro_retries}")

        if self.intro_retry_count >= self.max_intro_retries:
            self.intro_done = True
            self.stage = "icebreaker"
            print("[DEBUG] Intro max retries hit. Now transitioning to icebreaker.")
            return self.handle_icebreaker_stage("", on_token=on_token)  # 👈 Trigger icebreaker immediately

        if on_token and reply:
            self._emit_stream_text(on_token, reply)

        return {
            "stage": "introduction",
            "message": reply
        }

# ===== BEGINING OF - ICE BREAKER STAGE  =====

    def handle_icebreaker_stage(self, user_input, on_token=None):
        
        log("handle_icebreaker_stage")

        if not self.icebreaker_question_asked:
            question = generate_icebreaker_question(
                self.job_title,
                conversation_history=self.conversation_history,
                on_token=on_token,
            )
            self.current_icebreaker = question
            self.conversation_history.append({"role": "assistant", "content": question})
            self.icebreaker_question_asked = True
            return {"stage": "icebreaker", "message": question}

        self.conversation_history.append({"role": "user", "content": user_input})
        result = assess_icebreaker_response(
            user_input,
            self.current_icebreaker,
            conversation_history=self.conversation_history,
        )
        print(f"[DEBUG] Icebreaker assessment → {result}")

        if result == "valid":
            self.icebreaker_done = True
            self.stage = "intro_followup"
            
            followup_q = generate_dynamic_question(
                self.job_title,
                self.job_description,
                self.conversation_history,
                on_token=on_token,
            )
            self.current_followup_question = followup_q
            self.conversation_history.append({"role": "assistant", "content": followup_q})

            return {
                "stage": "intro_followup",
                "message": f"Thanks for sharing that!\n\n{followup_q}"
            }

        self.icebreaker_retry_count += 1
        print(f"[DEBUG] Icebreaker retry: {self.icebreaker_retry_count}/{self.max_icebreaker_retries}")

        if self.icebreaker_retry_count >= self.max_icebreaker_retries:
            self.icebreaker_done = True
            self.stage = "intro_followup"
            
            # Immediately trigger follow-up question
            followup_q = generate_dynamic_question(
                self.job_title,
                self.job_description,
                self.conversation_history,
                on_token=on_token,
            )
            self.current_followup_question = followup_q
            self.conversation_history.append({"role": "assistant", "content": followup_q})

            return {
                "stage": "intro_followup",
                "message": f"Let’s move on anyway. Thanks!\n\n{followup_q}"
            }

        question = generate_icebreaker_question(
            self.job_title,
            conversation_history=self.conversation_history,
            on_token=on_token,
            is_retry=True,
        )
        self.current_icebreaker = question
        from Interview_functions import (
            _is_greeting_or_farewell,
            _looks_like_candidate_question,
        )
        if _looks_like_candidate_question(user_input):
            message = (
                "We'll get to technical topics later. "
                f"For now — {question}"
            )
        elif _is_greeting_or_farewell(user_input):
            message = f"We're still in the interview. {question}"
        else:
            message = question
        self.conversation_history.append({"role": "assistant", "content": message})
        return {"stage": "icebreaker", "message": message}

# ===== BEGGINING OF - INTRO FOLLOW-UP STAGE  =====

    def handle_intro_followup_stage(self, user_input, on_token=None):
        log("handle_intro_followup_stage")

        if not self.intro_followup_done and self.followup_retry_count < self.max_followup_retries:

            # If no input from candidate, ask a follow-up question based on history
            if not user_input.strip():
                question = generate_dynamic_question(
                    self.job_title,
                    self.job_description,
                    self.conversation_history,
                    on_token=on_token,
                )
                self.current_followup_question = question
                self.conversation_history.append({"role": "assistant", "content": question})
                return {"stage": "intro_followup", "message": question}

            # Candidate gave an answer → assess it
            self.conversation_history.append({"role": "user", "content": user_input})
            question = self.current_followup_question or "N/A"
            result = assess_followup_response(
                question,
                user_input,
                conversation_history=self.conversation_history,
            )
            print(f"[DEBUG] Follow-up Q: {question}")
            print(f"[DEBUG] Follow-up answer assessment → {result}")

            if result == "strong":
                self.intro_followup_done = True
                self.stage = "resume_discussion"

                # Immediately ask first resume question if available
                if not self.current_resume_question and self.core_questions:
                    self._pop_next_resume_question()
                    self.resume_followup_retry_count = 0
                    self.conversation_history.append({"role": "assistant", "content": self.current_resume_question})
                    return {
                        "stage": "resume_discussion",
                        "message": f"Thanks for sharing that! Let’s continue with your resume.\n\n{self.current_resume_question}",
                        "requires_code": self.current_coding_requirement
                    }

                return {
                    "stage": "resume_discussion",
                    "message": "Thanks for sharing that! Let’s continue with your resume."
                }


            self.followup_retry_count += 1
            print(f"[DEBUG] Follow-up retry {self.followup_retry_count}/{self.max_followup_retries}")

            if self.followup_retry_count >= self.max_followup_retries:
                self.intro_followup_done = True
                self.stage = "resume_discussion"

                # Immediately trigger resume question
                if not self.current_resume_question and self.core_questions:
                    self._pop_next_resume_question()
                    self.resume_followup_retry_count = 0
                    self.conversation_history.append({"role": "assistant", "content": self.current_resume_question})
                    return {
                        "stage": "resume_discussion",
                        "message": f"Thanks! Let’s continue with your resume.\n\n{self.current_resume_question}",
                        "requires_code": self.current_coding_requirement
                    }

                return {
                    "stage": "resume_discussion",
                    "message": "Thanks! Let’s continue with your resume."
                }

            # Retry with a tighter follow-up based on what was missing
            question = generate_dynamic_question(
                self.job_title,
                self.job_description,
                self.conversation_history,
                on_token=on_token,
                is_retry=True,
            )
            self.current_followup_question = question
            self.conversation_history.append({"role": "assistant", "content": question})
            return {"stage": "intro_followup", "message": question}

        # Already complete
        self.stage = "resume_discussion"
        return {"stage": "resume_discussion", "message": "Let’s move on to your resume now."}
    
# ===== BEGGINING OF - RESUME QUESTIONS DISCUSSION STAGE  =====

    def handle_resume_discussion_stage(self, user_input, on_token=None):
        log("handle_resume_discussion_stage")

        # 1. No active question? Ask the next one.
        if not self.current_resume_question:
            if not self.core_questions:
                return self._begin_candidate_questions_stage(
                    on_token=on_token,
                    preface="Thanks — that wraps up the resume discussion.",
                )

            self._pop_next_resume_question()
            self.resume_followup_retry_count = 0  # Reset retry count for each question
            self.conversation_history.append({"role": "assistant", "content": self.current_resume_question})
            return {"stage": "resume_discussion", "message": self.current_resume_question, "requires_code": self.current_coding_requirement}

        # 2. Waiting for answer
        if not user_input.strip():
            return {"stage": "resume_discussion", "message": "Take your time. I’m listening!"}

        self.conversation_history.append({"role": "user", "content": user_input})

        result = evaluate_resume_response(self.current_resume_question, user_input)
        self.evaluation_log.append({
            "stage": "resume",
            "question": self.current_resume_question,
            "response": user_input,
            "evaluation": result
        })

        print(f"[DEBUG] Resume Q evaluation: {result}")

        # 3. Evaluate response — weak, confused, and off_topic trigger follow-up questions
        if result == "strong":
            self.current_resume_question = ""

            # Ask the next question immediately if available
            if self.core_questions:
                self._pop_next_resume_question()
                self.resume_followup_retry_count = 0

                transitions = [
                    "Great, let’s move forward.",
                    "Alright, here’s another one.",
                    "Sounds good — next question coming up.",
                    "Thanks for that! Let’s continue.",
                    "Got it. Let’s dive into the next one.",
                    "That makes sense. Here's the next one.",
                    "Perfect — moving on.",
                    "Appreciate that. Let’s go ahead.",
                    "Cool. Let’s tackle the next question.",
                    "Awesome. Here comes another one."
                ]
                weak_transitions = [
                    "Thanks, let’s move to the next one.",
                    "Got it. I’ll continue with the next question.",
                    "Thanks for answering. Here’s the next one.",
                    "Understood. Let’s keep going.",
                ]
                transition = random.choice(transitions if result == "strong" else weak_transitions)

                self.conversation_history.append({"role": "assistant", "content": self.current_resume_question})
                return {
                    "stage": "resume_discussion",
                    "message": f"{transition}\n\n{self.current_resume_question}",
                    "requires_code": self.current_coding_requirement,
                }

            # If no more resume questions, skip custom and open candidate Q&A
            return self._begin_candidate_questions_stage(
                on_token=on_token,
                preface="Thanks! That wraps up the resume part.",
            )


        self.resume_followup_retry_count += 1
        print(f"[DEBUG] Retry count: {self.resume_followup_retry_count}")

        if self.resume_followup_retry_count >= self.max_resume_followup_retries:
            self.current_resume_question = ""
            
            # Immediately ask next question if available
            if self.core_questions:
                self._pop_next_resume_question()
                self.resume_followup_retry_count = 0
                self.conversation_history.append({"role": "assistant", "content": self.current_resume_question})
                return {
                    "stage": "resume_discussion",
                    "message": f"No worries — let’s move on to the next question.\n\n{self.current_resume_question}",
                    "requires_code": self.current_coding_requirement,
                }

            # No more resume questions — skip custom and open candidate Q&A
            return self._begin_candidate_questions_stage(
                on_token=on_token,
                preface="No worries — that wraps up the resume questions.",
            )



        # 4. Ask follow-up
        followup = self._build_resume_followup(user_input, on_token=on_token)
        self.conversation_history.append({"role": "assistant", "content": followup})
        return {"stage": "resume_discussion", "message": followup, "requires_code": self.current_coding_requirement}
    
# ===== BEGGINING OF - CUSTOM QUESTIONS DISCUSSION STAGE  =====

    def handle_custom_questions_stage(self, user_input, on_token=None):
        log("handle_custom_questions_stage")

        # Step 1: Ask a new custom question if not in progress
        if not self.current_custom_question:
            if not self.required_questions:
                # Custom stage disabled / empty — go straight to candidate Q&A
                return self._begin_candidate_questions_stage(on_token=on_token)


            self.current_custom_question = self.required_questions.pop(0)
            self.custom_followup_retry_count = 0
            self.custom_followup_evaluations = []
            self.conversation_history.append({"role": "assistant", "content": self.current_custom_question})
            return {"stage": "custom_questions", "message": self.current_custom_question}

        # Step 2: Evaluate the candidate's response
        # Step 2: Evaluate the candidate's response
        if not user_input.strip():
            return {"stage": "custom_questions", "message": "Take your time. I'm listening!"}

        self.conversation_history.append({"role": "user", "content": user_input})
        self.last_custom_response = user_input
        evaluation = evaluate_custom_response(self.current_custom_question, user_input)

        self.evaluation_log.append({
            "stage": "custom",
            "question": self.current_custom_question,
            "response": user_input,
            "evaluation": evaluation
        })

        print(f"[DEBUG] Evaluation → {evaluation}")

        if evaluation == "clear":
            self.current_custom_question = ""

            # If more custom questions, ask next one immediately
            if self.required_questions:
                self.current_custom_question = self.required_questions.pop(0)
                self.custom_followup_retry_count = 0
                self.custom_followup_evaluations = []

                transitions = [
                    "Great insight! Let’s try the next one.",
                    "Understood — here's the next question.",
                    "Appreciate that. Let’s keep going.",
                    "Alright, moving on to the next one.",
                    "Clear answer. Here's something else for you.",
                    "Got it! Let’s continue the conversation.",
                    "Thanks! I have another question for you.",
                    "Sounds good — next up!",
                    "Cool. Let’s keep it flowing.",
                    "That works. Let’s move forward."
                ]
                transition = random.choice(transitions)

                self.conversation_history.append({"role": "assistant", "content": self.current_custom_question})
                return {
                    "stage": "custom_questions",
                    "message": f"{transition}\n\n{self.current_custom_question}"
                }

            # No more custom questions, move to candidate Q&A
            return self._begin_candidate_questions_stage(
                on_token=on_token,
                preface="Thanks for the clear answer!",
            )


        # Step 3: Retry logic for unclear answers
        self.custom_followup_retry_count += 1
        self.custom_followup_evaluations.append(evaluation)
        print(f"[DEBUG] custom_followup_retry_count: {self.custom_followup_retry_count}")
        
        # Step 4: If limit hit, either show model answer or move on
        if self.custom_followup_retry_count >= self.max_custom_followup_retries:
            if all(ev in ["weak", "confused", "no_answer", "off_topic"] for ev in self.custom_followup_evaluations):
                model_answer = generate_model_answer(self.current_custom_question, on_token=on_token)
                reply = f"No worries — let me explain.\n\n{model_answer}"
            else:
                reply = "Thanks for your effort — let’s continue."
            
            self.current_custom_question = ""
            return {"stage": "custom_questions", "message": reply}

        # Step 5: Ask follow-up question
        followup = generate_custom_followup(self.current_custom_question, user_input, on_token=on_token)
        if (followup or "").strip().lower() == (self.current_custom_question or "").strip().lower():
            followup = "Could you expand on that with a more specific example or outcome?"
        self.conversation_history.append({"role": "assistant", "content": followup})
        return {"stage": "custom_questions", "message": followup}

# ===== BEGGINING OF - END OF INTERVIEW CANDIDATE QUESTION DISCUSSION STAGE  =====

    def handle_candidate_questions_stage(self, user_input, on_token=None):
        log("handle_candidate_questions_stage")

        # Step 1: If blank input → trigger prompt
        if not user_input.strip():
            self.conversation_history.append({"role": "assistant", "content": "I think we’ve reached the end of this interview. Do you have any questions for me before we wrap up?"})
            return {
                "stage": "candidate_questions",
                "message": "I think we’ve reached the end of this interview. Do you have any questions for me before we wrap up?"
            }

        at_max = self.candidate_question_count >= self.max_candidate_questions
        remaining = max(self.max_candidate_questions - self.candidate_question_count, 0)

        self.conversation_history.append({"role": "user", "content": user_input})
        turn = run_candidate_qna_turn(
            user_input=user_input,
            conversation_history=self.conversation_history,
            evaluation_log=self.evaluation_log,
            job_title=self.job_title,
            job_description=self.job_description,
            questions_remaining=remaining,
            last_chance=at_max or remaining <= 1,
            on_token=on_token,
            interviewer_name=getattr(self, "interviewer_name", None) or "Sadhan",
        )
        intent = turn.get("intent") or "unclear"
        reply = (turn.get("reply") or "").strip()
        print(
            f"[DEBUG] candidate_qna intent={intent} "
            f"count={self.candidate_question_count}/{self.max_candidate_questions} "
            f"should_count={turn.get('should_count_as_question')} "
            f"ready_to_end={turn.get('ready_to_end')}"
        )

        # Soft limit already hit: allow one last real question answer, otherwise lock.
        if at_max:
            if intent == "ask_question" and reply:
                return self._prompt_manual_end(
                    f"{reply}\n\n"
                    "Thanks for your questions. Please press the End Interview button for your feedback."
                )
            if intent == "decline":
                return self._prompt_manual_end(
                    reply or "Please press the End Interview button for your feedback."
                )
            return self._prompt_manual_end(
                "That's all the time we have for questions. "
                "Please press the End Interview button for your feedback."
            )

        # Clear decline → Option B lock
        if intent == "decline" or turn.get("ready_to_end"):
            return self._prompt_manual_end(
                reply or "Thanks — please press the End Interview button for your feedback."
            )

        # Greeting / unclear / wants_to_ask / personal_or_meta → stay open, do not consume a question slot
        if intent in {"greeting_or_chitchat", "unclear", "wants_to_ask", "personal_or_meta"}:
            message = reply or "Sure — do you have any questions about the role before we wrap up?"
            self.conversation_history.append({"role": "assistant", "content": message})
            return {
                "stage": "candidate_questions",
                "message": message,
                "awaiting_manual_end": False,
            }

        # Real question answered
        if not reply:
            reply = "Happy to help — what would you like to know about the role?"
            self.conversation_history.append({"role": "assistant", "content": reply})
            return {
                "stage": "candidate_questions",
                "message": reply,
                "awaiting_manual_end": False,
            }

        if turn.get("should_count_as_question", True):
            self.candidate_question_count += 1
        remaining = self.max_candidate_questions - self.candidate_question_count
        print(
            f"[DEBUG] candidate_question_count: "
            f"{self.candidate_question_count}/{self.max_candidate_questions} — remaining: {remaining}"
        )

        if self.candidate_question_count >= self.max_candidate_questions:
            return self._prompt_manual_end(
                f"{reply}\n\n"
                "That's all the time we have for your questions. "
                "Please press the End Interview button for your feedback."
            )

        if self.candidate_question_count == self.max_candidate_questions - 1:
            final_prompt = "You can ask one more question, or press End Interview when you're ready."
            message = f"{reply}\n\n{final_prompt}"
            self.conversation_history.append({"role": "assistant", "content": message})
            return {
                "stage": "candidate_questions",
                "message": message,
                "awaiting_manual_end": False,
            }

        followups = [
            "Anything else you'd like to ask before we wrap up?",
            "Do you have any other questions for me?",
            "Is there anything you're curious about before we end?",
            "Would you like to ask anything else before we conclude?",
        ]
        followup = random.choice(followups)
        message = f"{reply}\n\n{followup}"
        self.conversation_history.append({"role": "assistant", "content": message})
        return {
            "stage": "candidate_questions",
            "message": message,
            "awaiting_manual_end": False,
        }


# ===== BEGGINING OF - END OF INTERVIEW CANDIDATE EVALUATION STAGE  =====

    def handle_wrapup_evaluation(self):
        log("handle_wrapup_evaluation")

        from Interview_functions import (
            analyze_individual_responses,
            generate_final_summary_review
        )

        print("Interview Assistant: Thank you! Let me summarize your interview.")

        detailed_log = analyze_individual_responses(self.evaluation_log, model=self.model)

        evaluation_result = generate_final_summary_review(
            self.job_title,
            self.conversation_history,
            detailed_log,
            model=self.model
        )

        self.final_summary = evaluation_result['summary']
        self.final_evaluation_log = detailed_log
        self.key_strengths = evaluation_result['key_strengths']
        self.improvement_areas = evaluation_result['improvement_areas']
        self.overall_rating = evaluation_result['overall_rating']
        self.metrics = evaluation_result.get('metrics', {})

        print(f"\nFinal Evaluation:\n{evaluation_result['summary']}")
        print(f"\nKey Strengths:\n{evaluation_result['key_strengths']}")
        print(f"\nImprovement Areas:\n{evaluation_result['improvement_areas']}")
        print(f"\nOverall Rating: {evaluation_result['overall_rating']:.1f}/10")
        print("[INFO] Interview evaluation completed - data ready for database storage.")

        return {
            "stage": "done",
            "message": "Thanks again — this concludes the interview. Final evaluation saved.",
            "interview_done": True,
            "summary": evaluation_result['summary'],
            "key_strengths": evaluation_result['key_strengths'],
            "improvement_areas": evaluation_result['improvement_areas'],
            "overall_rating": evaluation_result['overall_rating']
        }
