"""One Ollama call per interview turn with optional token streaming."""
from __future__ import annotations

import json
import os
import random
import re
from typing import Callable, Optional

from Interview_functions import (
    generate_icebreaker_question,
    generate_dynamic_question,
    log,
    ollama_chat_stream,
)

META_MARKER = "\nMETA_JSON:"


def unified_turns_enabled() -> bool:
    return os.getenv("INTERVIEW_UNIFIED_TURNS", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }


def _model_name() -> str:
    return os.getenv("OLLAMA_MODEL", "llama3.2:3b").strip() or "llama3.2:3b"


def build_turn_context(manager) -> dict:
    pending_resume = ""
    if manager.core_questions:
        pending_resume = (manager.core_questions[0].get("question") or "").strip()
    pending_custom = (manager.required_questions[0] if manager.required_questions else "") or ""
    if isinstance(pending_custom, dict):
        pending_custom = pending_custom.get("question", "")
    return {
        "stage": manager.stage,
        "intro_done": manager.intro_done,
        "job_qna_done": manager.job_qna_done,
        "job_description_shown": manager.job_description_shown,
        "intro_retry_count": manager.intro_retry_count,
        "max_intro_retries": manager.max_intro_retries,
        "icebreaker_done": manager.icebreaker_done,
        "icebreaker_question_asked": manager.icebreaker_question_asked,
        "current_icebreaker": manager.current_icebreaker,
        "icebreaker_retry_count": manager.icebreaker_retry_count,
        "intro_followup_done": manager.intro_followup_done,
        "current_followup_question": manager.current_followup_question,
        "followup_retry_count": manager.followup_retry_count,
        "current_resume_question": manager.current_resume_question,
        "pending_resume_question": pending_resume,
        "resume_followup_retry_count": manager.resume_followup_retry_count,
        "current_custom_question": manager.current_custom_question,
        "pending_custom_question": str(pending_custom).strip(),
        "custom_followup_retry_count": manager.custom_followup_retry_count,
        "candidate_question_count": manager.candidate_question_count,
        "max_candidate_questions": manager.max_candidate_questions,
        "job_title": manager.job_title,
        "has_core_questions": bool(manager.core_questions),
        "has_custom_questions": bool(manager.required_questions),
        "requires_code": bool(getattr(manager, "current_coding_requirement", False)),
    }


def _build_system_prompt(ctx: dict, user_input: str) -> str:
    stage = ctx["stage"]
    rules = """
You are a professional AI interviewer. Reply naturally in 1-4 sentences (no markdown).

Output format (strict):
1) Candidate-facing reply (plain text only).
2) Blank line, then a line: META_JSON:
3) One line of compact JSON with keys:
   message (repeat reply), assessment, intro_status, job_explained, advance_stage, has_candidate_question

assessment values: strong, weak, valid, clear, confused, off_topic, no_answer, continue, wait, retry, yes, no
intro_status (intro only): continue, wait, retry
job_explained: true only if you explained the role this turn
advance_stage: true when the candidate should move to the next interview phase after this reply
has_candidate_question: true/false during candidate_questions when they asked something real

Rules by stage:
- introduction: decide intro_status; continue when they shared background; explain job only if asked
- icebreaker: assess their answer to the icebreaker; valid if substantive; if advancing include a warm transition
- intro_followup: assess follow-up answer; strong advances to resume
- resume_discussion: assess answer to current resume question; weak = give a short follow-up in message; strong = short praise only (next question is added by server)
- custom_questions: assess clarity; weak = brief follow-up in message
- candidate_questions: answer their question professionally; has_candidate_question yes/no; advance when they have no more questions
"""
    return f"""{rules}
Job: {ctx['job_title']}
Stage: {stage}
Context: {json.dumps(ctx, default=str)}
User input: {user_input!r}
Current resume Q: {ctx.get('current_resume_question') or 'none'}
Current custom Q: {ctx.get('current_custom_question') or 'none'}
Icebreaker Q: {ctx.get('current_icebreaker') or 'none'}
"""


def _parse_stream_result(raw: str) -> dict:
    text = (raw or "").strip()
    meta = {}
    visible = text
    if META_MARKER in text:
        visible, meta_blob = text.split(META_MARKER, 1)
        visible = visible.strip()
        meta_line = meta_blob.strip().splitlines()[0] if meta_blob.strip() else "{}"
        try:
            meta = json.loads(meta_line)
        except Exception:
            try:
                start = meta_blob.find("{")
                end = meta_blob.rfind("}")
                if start >= 0 and end > start:
                    meta = json.loads(meta_blob[start : end + 1])
            except Exception:
                meta = {}
    message = (meta.get("message") or visible or "Thanks for sharing that.").strip()
    return {
        "message": message,
        "assessment": (meta.get("assessment") or "wait").strip().lower(),
        "intro_status": (meta.get("intro_status") or "wait").strip().lower(),
        "job_explained": bool(meta.get("job_explained")),
        "advance_stage": bool(meta.get("advance_stage")),
        "has_candidate_question": (meta.get("has_candidate_question") or "yes").strip().lower(),
    }


def conduct_unified_turn(
    manager,
    user_input: str,
    on_token: Optional[Callable[[str], None]] = None,
) -> dict:
    log("conduct_unified_turn")
    ctx = build_turn_context(manager)
    if not ctx["icebreaker_question_asked"] and ctx["stage"] == "icebreaker" and not user_input.strip():
        q = generate_icebreaker_question(ctx["job_title"])
        return {
            "message": q,
            "assessment": "ask",
            "intro_status": "wait",
            "job_explained": False,
            "advance_stage": False,
            "has_candidate_question": "no",
        }

    system = _build_system_prompt(ctx, user_input)
    messages = [{"role": "system", "content": system}]
    messages.extend(manager.conversation_history[-12:])
    messages.append({"role": "user", "content": user_input or "(no message)"})

    buffer = ""
    streamed_len = 0
    model = _model_name()
    try:
        for chunk in ollama_chat_stream(model=model, messages=messages):
            buffer += chunk
            if META_MARKER in buffer:
                visible = buffer.split(META_MARKER, 1)[0]
            else:
                visible = buffer
            new_text = visible[streamed_len:]
            streamed_len = len(visible)
            if new_text and on_token:
                on_token(new_text)
        return _parse_stream_result(buffer)
    except Exception as exc:
        print(f"[ERROR] conduct_unified_turn failed: {exc}")
        return {
            "message": "Thanks for sharing that. Could you add a bit more detail?",
            "assessment": "retry",
            "intro_status": "wait",
            "job_explained": False,
            "advance_stage": False,
            "has_candidate_question": "no",
        }


def apply_unified_turn(manager, parsed: dict, user_input: str) -> dict:
    """Apply LLM result to manager state; mirrors legacy stage handlers."""
    log("apply_unified_turn")
    stage = manager.stage
    message = parsed.get("message") or "Thanks for sharing that."
    assessment = (parsed.get("assessment") or "wait").strip().lower()
    intro_status = (parsed.get("intro_status") or "wait").strip().lower()

    if user_input.strip():
        manager.conversation_history.append({"role": "user", "content": user_input})

    # --- Introduction ---
    if not manager.intro_done:
        manager.conversation_history.append({"role": "assistant", "content": message})
        if parsed.get("job_explained"):
            manager.job_description_shown = True
            manager.intro_retry_count = 0
        if intro_status == "continue" or assessment == "continue":
            manager.job_qna_done = True
            manager.intro_done = True
            manager.intro_retry_count = 0
            manager.stage = "icebreaker"
            if not manager.icebreaker_question_asked:
                q = message if "?" in message else generate_icebreaker_question(manager.job_title)
                manager.current_icebreaker = q
                manager.icebreaker_question_asked = True
                manager.conversation_history.append({"role": "assistant", "content": q})
                return {"stage": "icebreaker", "message": q}
            return {"stage": "icebreaker", "message": message}
        manager.intro_retry_count += 1
        if manager.intro_retry_count >= manager.max_intro_retries:
            manager.intro_done = True
            manager.stage = "icebreaker"
            return apply_unified_turn(
                manager,
                {
                    "message": generate_icebreaker_question(manager.job_title),
                    "assessment": "ask",
                    "intro_status": "wait",
                },
                "",
            )
        return {"stage": "introduction", "message": message}

    # --- Icebreaker ---
    if not manager.icebreaker_done:
        if not manager.icebreaker_question_asked:
            q = message or generate_icebreaker_question(manager.job_title)
            manager.current_icebreaker = q
            manager.icebreaker_question_asked = True
            manager.conversation_history.append({"role": "assistant", "content": q})
            return {"stage": "icebreaker", "message": q}
        manager.conversation_history.append({"role": "assistant", "content": message})
        if assessment in {"valid", "strong", "continue"} or parsed.get("advance_stage"):
            manager.icebreaker_done = True
            manager.stage = "intro_followup"
            fq = message if "?" in message else generate_dynamic_question(
                manager.job_title, manager.job_description, manager.conversation_history
            )
            manager.current_followup_question = fq
            manager.conversation_history.append({"role": "assistant", "content": fq})
            return {"stage": "intro_followup", "message": f"Thanks for sharing that!\n\n{fq}"}
        manager.icebreaker_retry_count += 1
        if manager.icebreaker_retry_count >= manager.max_icebreaker_retries:
            manager.icebreaker_done = True
            manager.stage = "intro_followup"
            fq = generate_dynamic_question(
                manager.job_title, manager.job_description, manager.conversation_history
            )
            manager.current_followup_question = fq
            manager.conversation_history.append({"role": "assistant", "content": fq})
            return {"stage": "intro_followup", "message": f"Let's move on anyway.\n\n{fq}"}
        q = message if "?" in message else generate_icebreaker_question(manager.job_title)
        manager.current_icebreaker = q
        manager.conversation_history.append({"role": "assistant", "content": q})
        return {"stage": "icebreaker", "message": q}

    # --- Intro follow-up ---
    if not manager.intro_followup_done:
        if not user_input.strip():
            q = message if "?" in message else generate_dynamic_question(
                manager.job_title, manager.job_description, manager.conversation_history
            )
            manager.current_followup_question = q
            manager.conversation_history.append({"role": "assistant", "content": q})
            return {"stage": "intro_followup", "message": q}
        manager.conversation_history.append({"role": "assistant", "content": message})
        if assessment == "strong" or parsed.get("advance_stage"):
            manager.intro_followup_done = True
            manager.stage = "resume_discussion"
            if not manager.current_resume_question and manager.core_questions:
                manager._pop_next_resume_question()
                manager.resume_followup_retry_count = 0
                manager.conversation_history.append(
                    {"role": "assistant", "content": manager.current_resume_question}
                )
                return {
                    "stage": "resume_discussion",
                    "message": f"Thanks for sharing that!\n\n{manager.current_resume_question}",
                    "requires_code": manager.current_coding_requirement,
                }
            return {"stage": "resume_discussion", "message": "Thanks! Let's continue with your resume."}
        manager.followup_retry_count += 1
        if manager.followup_retry_count >= manager.max_followup_retries:
            manager.intro_followup_done = True
            manager.stage = "resume_discussion"
            if manager.core_questions:
                manager._pop_next_resume_question()
                manager.conversation_history.append(
                    {"role": "assistant", "content": manager.current_resume_question}
                )
                return {
                    "stage": "resume_discussion",
                    "message": f"Thanks!\n\n{manager.current_resume_question}",
                    "requires_code": manager.current_coding_requirement,
                }
            return {"stage": "resume_discussion", "message": "Thanks! Let's continue with your resume."}
        q = message if "?" in message else generate_dynamic_question(
            manager.job_title, manager.job_description, manager.conversation_history
        )
        manager.current_followup_question = q
        manager.conversation_history.append({"role": "assistant", "content": q})
        return {"stage": "intro_followup", "message": q}

    # --- Resume ---
    if manager.stage == "resume_discussion":
        if not manager.current_resume_question:
            if not manager.core_questions:
                manager.stage = "custom_questions"
                return {"stage": "custom_questions", "message": "Great, let's move on to some custom questions now."}
            manager._pop_next_resume_question()
            manager.resume_followup_retry_count = 0
            manager.conversation_history.append({"role": "assistant", "content": manager.current_resume_question})
            return {
                "stage": "resume_discussion",
                "message": manager.current_resume_question,
                "requires_code": manager.current_coding_requirement,
            }
        if not user_input.strip():
            return {"stage": "resume_discussion", "message": "Take your time. I'm listening!"}
        manager.evaluation_log.append({
            "stage": "resume",
            "question": manager.current_resume_question,
            "response": user_input,
            "evaluation": assessment,
        })
        if assessment == "strong" or parsed.get("advance_stage"):
            manager.current_resume_question = ""
            if manager.core_questions:
                manager._pop_next_resume_question()
                manager.resume_followup_retry_count = 0
                transition = random.choice([
                    "Great, let's move forward.",
                    "Thanks for that! Let's continue.",
                    "Alright, here's another one.",
                ])
                msg = f"{transition}\n\n{manager.current_resume_question}"
                manager.conversation_history.append({"role": "assistant", "content": manager.current_resume_question})
                return {
                    "stage": "resume_discussion",
                    "message": msg,
                    "requires_code": manager.current_coding_requirement,
                }
            manager.stage = "custom_questions"
            if manager.required_questions:
                manager.current_custom_question = manager.required_questions.pop(0)
                if isinstance(manager.current_custom_question, dict):
                    manager.current_custom_question = manager.current_custom_question.get("question", "")
                manager.custom_followup_retry_count = 0
                manager.conversation_history.append({"role": "assistant", "content": manager.current_custom_question})
                return {
                    "stage": "custom_questions",
                    "message": "Thanks! That wraps up the resume part.\n\n" + manager.current_custom_question,
                }
            return {"stage": "done", "message": "Thanks! That wraps up the resume part."}
        manager.resume_followup_retry_count += 1
        if manager.resume_followup_retry_count >= manager.max_resume_followup_retries:
            manager.current_resume_question = ""
            if manager.core_questions:
                manager._pop_next_resume_question()
                manager.conversation_history.append({"role": "assistant", "content": manager.current_resume_question})
                return {
                    "stage": "resume_discussion",
                    "message": f"No worries — next question.\n\n{manager.current_resume_question}",
                    "requires_code": manager.current_coding_requirement,
                }
            manager.stage = "custom_questions"
            return {"stage": "custom_questions", "message": "Let's move on to custom questions."}
        manager.conversation_history.append({"role": "assistant", "content": message})
        return {
            "stage": "resume_discussion",
            "message": message,
            "requires_code": manager.current_coding_requirement,
        }

    # --- Custom ---
    if manager.stage == "custom_questions":
        if not manager.current_custom_question:
            if not manager.required_questions:
                manager.custom_qna_done = True
                manager.stage = "candidate_questions"
                return {
                    "stage": "candidate_questions",
                    "message": "Thanks! Before we wrap up, do you have any questions for me?",
                }
            manager.current_custom_question = manager.required_questions.pop(0)
            if isinstance(manager.current_custom_question, dict):
                manager.current_custom_question = manager.current_custom_question.get("question", "")
            manager.custom_followup_retry_count = 0
            manager.conversation_history.append({"role": "assistant", "content": manager.current_custom_question})
            return {"stage": "custom_questions", "message": manager.current_custom_question}
        if not user_input.strip():
            return {"stage": "custom_questions", "message": "Take your time. I'm listening!"}
        manager.evaluation_log.append({
            "stage": "custom",
            "question": manager.current_custom_question,
            "response": user_input,
            "evaluation": assessment,
        })
        if assessment == "clear" or parsed.get("advance_stage"):
            manager.current_custom_question = ""
            if manager.required_questions:
                manager.current_custom_question = manager.required_questions.pop(0)
                if isinstance(manager.current_custom_question, dict):
                    manager.current_custom_question = manager.current_custom_question.get("question", "")
                manager.conversation_history.append({"role": "assistant", "content": manager.current_custom_question})
                return {"stage": "custom_questions", "message": manager.current_custom_question}
            manager.stage = "candidate_questions"
            return {
                "stage": "candidate_questions",
                "message": "Thanks! Do you have any questions for me before we wrap up?",
            }
        manager.custom_followup_retry_count += 1
        manager.conversation_history.append({"role": "assistant", "content": message})
        return {"stage": "custom_questions", "message": message}

    # --- Candidate questions ---
    if manager.stage == "candidate_questions":
        if not user_input.strip():
            prompt = "Do you have any questions for me before we wrap up?"
            manager.conversation_history.append({"role": "assistant", "content": prompt})
            return {"stage": "candidate_questions", "message": prompt}
        has_q = parsed.get("has_candidate_question") == "yes" or assessment == "yes"
        manager.conversation_history.append({"role": "assistant", "content": message})
        if not has_q:
            manager.candidate_qna_done = True
            manager.stage = "wrapup_evaluation"
            return {
                "stage": "wrapup_evaluation",
                "message": "Please press the END interview button to end the interview.",
                "interview_done": False,
            }
        manager.candidate_question_count += 1
        if manager.candidate_question_count >= manager.max_candidate_questions:
            manager.candidate_qna_done = True
            manager.stage = "wrapup_evaluation"
            return {
                "stage": "wrapup_evaluation",
                "message": message + "\n\nPlease press the END interview button to end the interview.",
                "interview_done": False,
            }
        followups = [
            "Anything else you'd like to ask before we wrap up?",
            "Do you have any other questions for me?",
        ]
        return {"stage": "candidate_questions", "message": f"{message}\n\n{random.choice(followups)}"}

    manager.conversation_history.append({"role": "assistant", "content": message})
    return {
        "stage": "done",
        "message": message or "All stages complete. Press END Interview when ready.",
        "interview_done": False,
    }


def receive_input_unified(manager, user_input: str, on_token=None) -> dict:
    parsed = conduct_unified_turn(manager, user_input, on_token=on_token)
    return apply_unified_turn(manager, parsed, user_input)
