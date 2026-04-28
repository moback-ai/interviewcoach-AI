import json
import random
import time

from Interview_functions import (
    log,
    assess_intro_progress,
    generate_contextual_intro_reply,
    generate_icebreaker_question,
    assess_icebreaker_response,
    generate_icebreaker_question,
    assess_icebreaker_response,
    assess_followup_response,
    generate_dynamic_question,
    evaluate_resume_response,
    generate_followup_question,
    evaluate_custom_response,
    generate_custom_followup,
    generate_model_answer,
    assess_candidate_has_question,
    generate_candidate_qna_response
    # ✅ REMOVED: generate_key_strengths_and_improvements - no longer needed
)


class InterviewManager:
    def __init__(self, model="llama3", config_path="interview_config.json"):
        self.model = model
        self.api_call_count = 0
        self.stage = "introduction"
        self.conversation_history = []

        # Load config
        with open(config_path, "r") as f:
            config = json.load(f)

        self.job_title = config.get("job_title", "this role")
        self.job_description = config.get("job_description", "")
        self.interview_style = config.get("interview_style", "conversational")
        self.required_questions = config.get("custom_questions", [])
        self.core_questions = config.get("core_questions", [])
        self.coding_requirement = config.get("coding_requirement", "")
        self.icebreakers = config.get("icebreakers", [])

# ========= Interview Time Limit ==================
        self.start_time = None
        self.time_limit_seconds = config.get("time_limit_minutes", 150) * 60  # Default: 2 hours


# ========= Stage Flags ==================

        # === Intro Flags ===
        self.intro_done = False
        self.job_qna_done = False
        self.job_description_shown = False
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

        # Custom Questions
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

        # Candidate evaluation
        self.evaluation_log = []


        # === Initial greeting ===
        greeting = f"Welcome to the interview for the role of {self.job_title}. Let’s get started!"
        print(f"\n {greeting}\n")
        self.conversation_history.append({"role": "assistant", "content": greeting})

    def _question_key(self, text):
        return " ".join((text or "").strip().lower().split())

    def _ensure_runtime_state(self):
        if not hasattr(self, "asked_question_texts") or not isinstance(self.asked_question_texts, list):
            self.asked_question_texts = []
        if not hasattr(self, "current_resume_question_obj"):
            self.current_resume_question_obj = None
        if self.core_questions is None:
            self.core_questions = []

    def _has_asked_question(self, text):
        key = self._question_key(text)
        return bool(key) and key in self.asked_question_texts

    def _mark_question_asked(self, text):
        key = self._question_key(text)
        if key and key not in self.asked_question_texts:
            self.asked_question_texts.append(key)

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

    def _build_resume_followup(self, user_input):
        followup = generate_followup_question(self.current_resume_question, user_input)
        if (
            (followup or "").strip().lower() == (self.current_resume_question or "").strip().lower()
            or self._has_asked_question(followup)
        ):
            followup = "Could you walk me through that with a concrete example from your experience?"
        if self._has_asked_question(followup):
            followup = "What was your specific role in that example, and what outcome did your work create?"
        self._mark_question_asked(followup)
        return followup

    def is_time_exceeded(self):
        if self.start_time is None:
            return False  # Timer not started yet
        elapsed = time.time() - self.start_time
        return elapsed >= self.time_limit_seconds


    def receive_input(self, user_input: str):
        self._ensure_runtime_state()
        self.api_call_count += 1
        print(f"[INFO] API call #{self.api_call_count} | Stage: {self.stage}")
        
        if self.start_time is None:
            self.start_time = time.time()
            print("[DEBUG] Interview timer started.")

        # ✅ NEW: Handle manual interview end command
        if user_input.strip().upper() == "END_INTERVIEW":
            print("[INFO] Manual interview end requested by user")
            self.stage = "wrapup_evaluation"
            return {
                "stage": "manual_end",
                "message": "Thank you for completing the interview. Let me provide you with a comprehensive evaluation.",
                **self.handle_wrapup_evaluation()  # ✅ This already includes "interview_done": True
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
            return self.handle_intro_stage(user_input)

        if not self.icebreaker_done:
            return self.handle_icebreaker_stage(user_input)

        if not self.intro_followup_done:
            return self.handle_intro_followup_stage(user_input)
        if self.stage == "resume_discussion":
            return self.handle_resume_discussion_stage(user_input)
        if self.stage == "custom_questions":
            return self.handle_custom_questions_stage(user_input)
        if self.stage == "candidate_questions":
            return self.handle_candidate_questions_stage(user_input)
        return {
            "stage": "done",
            "message": "All stages complete. Please press the END Interview Button to end the interview.",
            "interview_done": False  # ✅ So your app can differentiate
        }


# ===== BEGINING OF - INTRO STAGE  =====

    def handle_intro_stage(self, user_input):
        from Interview_functions import log
        log("handle_intro_stage")

        self.conversation_history.append({"role": "user", "content": user_input})

        # === Always generate contextual reply (handles job + intro flow) ===
        result = generate_contextual_intro_reply(self.job_title,self.job_description,self.conversation_history,user_input)
        reply = result["message"]
        self.conversation_history.append({"role": "assistant", "content": reply})

        if result["job_explained"]:
            self.job_description_shown = True
            self.intro_retry_count = 0
            print("[DEBUG] Job explanation confirmed by LLM. Resetting retry count and setting job_description_shown = True")


        if self.job_description_shown and not self.job_qna_done:
            job_done_check = assess_intro_progress(self.conversation_history)
            if job_done_check == "continue":
                self.job_qna_done = True
                print("[DEBUG] Job Q&A finished. Marking job_qna_done = True")

        # === If job is fully done, assess intro normally ===
        intro_status = assess_intro_progress(self.conversation_history)
        print(f"[DEBUG] assess_intro_progress → {intro_status}")

        if intro_status == "continue":
            self.intro_done = True
            self.intro_retry_count = 0
            self.stage = "icebreaker"

            # Immediately ask the icebreaker
            question = generate_icebreaker_question(self.job_title)
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
            return self.handle_icebreaker_stage("")  # 👈 Trigger icebreaker immediately

        return {
            "stage": "introduction",
            "message": reply
        }

# ===== BEGINING OF - ICE BREAKER STAGE  =====

    def handle_icebreaker_stage(self, user_input):
        
        log("handle_icebreaker_stage")

        if not self.icebreaker_question_asked:
            question = generate_icebreaker_question(self.job_title)
            self.current_icebreaker = question
            self.conversation_history.append({"role": "assistant", "content": question})
            self.icebreaker_question_asked = True
            return {"stage": "icebreaker", "message": question}

        self.conversation_history.append({"role": "user", "content": user_input})
        result = assess_icebreaker_response(user_input, self.current_icebreaker)   
        print(f"[DEBUG] Icebreaker assessment → {result}")

        if result == "valid":
            self.icebreaker_done = True
            self.stage = "intro_followup"
            
            followup_q = generate_dynamic_question(self.job_title, self.job_description, self.conversation_history)
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
            followup_q = generate_dynamic_question(self.job_title, self.job_description, self.conversation_history)
            self.current_followup_question = followup_q
            self.conversation_history.append({"role": "assistant", "content": followup_q})

            return {
                "stage": "intro_followup",
                "message": f"Let’s move on anyway. Thanks!\n\n{followup_q}"
            }


        question = generate_icebreaker_question(self.job_title)
        self.current_icebreaker = question
        self.conversation_history.append({"role": "assistant", "content": question})
        return {"stage": "icebreaker", "message": question}

# ===== BEGGINING OF - INTRO FOLLOW-UP STAGE  =====

    def handle_intro_followup_stage(self, user_input):
        log("handle_intro_followup_stage")

        if not self.intro_followup_done and self.followup_retry_count < self.max_followup_retries:

            # If no input from candidate, ask a follow-up question based on history
            if not user_input.strip():
                question = generate_dynamic_question(self.job_title, self.job_description, self.conversation_history)
                self.current_followup_question = question
                self.conversation_history.append({"role": "assistant", "content": question})
                return {"stage": "intro_followup", "message": question}

            # Candidate gave an answer → assess it
            self.conversation_history.append({"role": "user", "content": user_input})
            question = self.current_followup_question or "N/A"
            result = assess_followup_response(question, user_input)
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

            # Retry with a new question
            question = generate_dynamic_question(self.job_title, self.job_description, self.conversation_history)
            self.current_followup_question = question
            self.conversation_history.append({"role": "assistant", "content": question})
            return {"stage": "intro_followup", "message": question}

        # Already complete
        self.stage = "resume_discussion"
        return {"stage": "resume_discussion", "message": "Let’s move on to your resume now."}
    
# ===== BEGGINING OF - RESUME QUESTIONS DISCUSSION STAGE  =====

    def handle_resume_discussion_stage(self, user_input):
        log("handle_resume_discussion_stage")

        # 1. No active question? Ask the next one.
        if not self.current_resume_question:
            if not self.core_questions:
                self.stage = "custom_questions"
                return {"stage": "custom_questions", "message": "Great, let’s move on to some custom questions now."}

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

        # 3. Evaluate response
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
                transition = random.choice(transitions)

                self.conversation_history.append({"role": "assistant", "content": self.current_resume_question})
                return {
                    "stage": "resume_discussion",
                    "message": f"{transition}\n\n{self.current_resume_question}",
                    "requires_code": self.current_coding_requirement,
                }

            # If no more resume questions, move to custom stage
            self.stage = "custom_questions"
            if self.required_questions:
                self.current_custom_question = self.required_questions.pop(0)
                self.custom_followup_retry_count = 0
                self.conversation_history.append({"role": "assistant", "content": self.current_custom_question})
                return {
                    "stage": "custom_questions",
                    "message": "Thanks! That wraps up the resume part.\n\n" + self.current_custom_question
                }

            return {
                "stage": "done",
                "message": "Thanks! That wraps up the resume part. Appreciate your answers."
            }


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

            # No more resume questions, move forward
            self.stage = "custom_questions"
            if self.required_questions:
                self.current_custom_question = self.required_questions.pop(0)
                self.custom_followup_retry_count = 0
                self.custom_followup_evaluations = []
                self.conversation_history.append({"role": "assistant", "content": self.current_custom_question})
                return {
                    "stage": "custom_questions",
                    "message": "No worries — that wraps up the resume questions. Let’s move on\n" + self.current_custom_question
                }
            else:
                return {
                    "stage": "done",
                    "message": "No worries — that wraps up the resume questions. Thanks for participating!"
                }



        # 4. Ask follow-up
        followup = self._build_resume_followup(user_input)
        self.conversation_history.append({"role": "assistant", "content": followup})
        return {"stage": "resume_discussion", "message": followup, "requires_code": self.current_coding_requirement}
    
# ===== BEGGINING OF - CUSTOM QUESTIONS DISCUSSION STAGE  =====

    def handle_custom_questions_stage(self, user_input):
        log("handle_custom_questions_stage")

        # Step 1: Ask a new custom question if not in progress
        if not self.current_custom_question:
            if not self.required_questions:
                # No more custom questions, move to candidate Q&A
                self.custom_qna_done = True  #  mark custom QnA as complete
                self.stage = "candidate_questions"
                return {
                    "stage": "candidate_questions",
                    "message": "Thanks for the answers! Before we wrap up, do you have any questions for me?"
                }


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
            self.stage = "candidate_questions"
            return {
                "stage": "candidate_questions",
                "message": "Thanks for the clear answer! Before we wrap up, do you have any questions for me?"
            }


        # Step 3: Retry logic for unclear answers
        self.custom_followup_retry_count += 1
        self.custom_followup_evaluations.append(evaluation)
        print(f"[DEBUG] custom_followup_retry_count: {self.custom_followup_retry_count}")
        
        # Step 4: If limit hit, either show model answer or move on
        if self.custom_followup_retry_count >= self.max_custom_followup_retries:
            if all(ev in ["weak", "confused", "no_answer", "off_topic"] for ev in self.custom_followup_evaluations):
                model_answer = generate_model_answer(self.current_custom_question)
                reply = f"No worries — let me explain.\n\n{model_answer}"
            else:
                reply = "Thanks for your effort — let’s continue."
            
            self.current_custom_question = ""
            return {"stage": "custom_questions", "message": reply}

        # Step 5: Ask follow-up question
        followup = generate_custom_followup(self.current_custom_question, user_input)
        if (followup or "").strip().lower() == (self.current_custom_question or "").strip().lower():
            followup = "Could you expand on that with a more specific example or outcome?"
        self.conversation_history.append({"role": "assistant", "content": followup})
        return {"stage": "custom_questions", "message": followup}

# ===== BEGGINING OF - END OF INTERVIEW CANDIDATE QUESTION DISCUSSION STAGE  =====

    def handle_candidate_questions_stage(self, user_input):
        log("handle_candidate_questions_stage")

        # Step 1: If blank input → trigger prompt
        if not user_input.strip():
            self.conversation_history.append({"role": "assistant", "content": "I think we’ve reached the end of this interview. Do you have any questions for me before we wrap up?"})
            return {
                "stage": "candidate_questions",
                "message": "I think we’ve reached the end of this interview. Do you have any questions for me before we wrap up?"
            }

        # Step 2: If already hit max, re-check if valid question before wrapping
        if self.candidate_question_count >= self.max_candidate_questions:
            decision = assess_candidate_has_question(user_input)
            if decision == "yes":
                reply = generate_candidate_qna_response(
                    user_question=user_input,
                    conversation_history=self.conversation_history,
                    evaluation_log=self.evaluation_log,
                    job_title=self.job_title,
                    last_chance=True
                )
                self.conversation_history.append({"role": "assistant", "content": reply})
                self.candidate_qna_done = True
                self.stage = "wrapup_evaluation"
                return {
                    "stage": "wrapup_evaluation",
                    "message": reply + "\n\nThanks again for your thoughtful questions — let me wrap up with a quick summary.",
                    **self.handle_wrapup_evaluation()
                }

            self.candidate_qna_done = True
            self.stage = "wrapup_evaluation"
            return self.handle_wrapup_evaluation()

        # Step 3: Otherwise, check if it's a real question
        self.conversation_history.append({"role": "user", "content": user_input})
        decision = assess_candidate_has_question(user_input)

        if decision == "no":
            self.candidate_qna_done = True
            self.stage = "wrapup_evaluation"
            # ✅ CHANGED: Show message instead of calling handle_wrapup_evaluation
            return {
                "stage": "wrapup_evaluation",
                "message": "Please press the END interview button to end the interview.",
                "interview_done": False  # Keep interview active until user manually ends
            }

        # Step 4: Answer the question
        last_chance = self.candidate_question_count == self.max_candidate_questions - 2
        reply = generate_candidate_qna_response(
            user_question=user_input,
            conversation_history=self.conversation_history,
            evaluation_log=self.evaluation_log,
            job_title=self.job_title,
            last_chance=last_chance
        )
        self.conversation_history.append({"role": "assistant", "content": reply})
        self.candidate_question_count += 1
        remaining = self.max_candidate_questions - self.candidate_question_count
        print(f"[DEBUG] candidate_question_count: {self.candidate_question_count}/{self.max_candidate_questions} — remaining: {remaining}")
       
        if self.candidate_question_count == self.max_candidate_questions:
            self.candidate_qna_done = True
            self.stage = "wrapup_evaluation"
            self.conversation_history.append({"role": "assistant", "content": reply})
            # ✅ CHANGED: Show message instead of calling handle_wrapup_evaluation
            return {
                "stage": "wrapup_evaluation",
                "message": reply + "\n\nPlease press the END interview button to end the interview.",
                "interview_done": False  # Keep interview active until user manually ends
            }


        # Step 6: If only 1 question remains, show the final clear prompt
        if self.candidate_question_count == self.max_candidate_questions - 1:
            final_prompt = "Let us end the interview here , Thankyou for your time "
            return {
                "stage": "candidate_questions",
                "message": f"{reply}\n\n{final_prompt}"
            }

        # Step 7: Otherwise, pick a friendly follow-up
        followups = [
            "Anything else you'd like to ask before we wrap up?",
            "Do you have any other questions for me?",
            "Is there anything you're curious about before we end?",
            "Would you like to ask anything else before we conclude?",
        ]
        followup = random.choice(followups)

        return {
            "stage": "candidate_questions",
            "message": f"{reply}\n\n{followup}"
        }


# ===== BEGGINING OF - END OF INTERVIEW CANDIDATE EVALUATION STAGE  =====

    def handle_wrapup_evaluation(self):
        log("handle_wrapup_evaluation")

        from Interview_functions import (
            analyze_individual_responses,
            generate_final_summary_review  # ✅ Only need this one function now
        )

        print("Interview Assistant: Thank you! Let me summarize your interview.")

        # 1. Analyze individual responses
        detailed_log = analyze_individual_responses(self.evaluation_log, model=self.model)
        
        # 2. Generate comprehensive evaluation (summary + strengths + improvements)
        evaluation_result = generate_final_summary_review(
            self.job_title,
            self.conversation_history,
            detailed_log,
            model=self.model
        )
        
        # ✅ Store all data for backend database storage
        self.final_summary = evaluation_result['summary']
        self.final_evaluation_log = detailed_log
        self.key_strengths = evaluation_result['key_strengths']
        self.improvement_areas = evaluation_result['improvement_areas']
        self.overall_rating = evaluation_result['overall_rating']
        self.metrics = evaluation_result.get('metrics', {})  # ✅ Add metrics storage
        
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
