import json
import os
import re

from common.llm.factory import chat as llm_chat, chat_stream as llm_chat_stream
from common.llm.ollama_provider import resolve_ollama_model_name
from common.runtime_config import optional_env as runtime_optional_env


RED = "\033[31m"
BOLD = "\033[1m"
BLUE = "\033[34m"
GREEN = "\033[32m"
CYAN = "\033[36m"
RESET = "\033[0m"


# Per-call temperatures for Bedrock Nova Lite (and Ollama). Global LLM_TEMPERATURE
# remains the fallback when callers omit an override.
TEMP_EVAL = 0.1       # classifiers / labelers (assess_*, evaluate_*)
TEMP_STRUCTURED = 0.2  # JSON scoring / summaries
TEMP_REPLY = 0.25      # short conversational interviewer replies
TEMP_QUESTION = 0.35   # icebreakers, follow-ups, dynamic questions


def _ollama_chat_options():
    """Cap generation length for faster interview turns (override via OLLAMA_NUM_PREDICT)."""
    raw = runtime_optional_env("OLLAMA_NUM_PREDICT", "384")
    try:
        num_predict = max(64, min(int(raw or 384), 1024))
    except (TypeError, ValueError):
        num_predict = 384
    return {"num_predict": num_predict, "temperature": 0.6}


def ollama_chat(*, model, messages, temperature=None, max_tokens=None):
    return llm_chat(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def sanitize_interviewer_display_text(text: str, *, streaming: bool = False) -> str:
    content = (text or "").strip()
    content = content.replace("[[job_explained]]", "").strip()
    if len(content) >= 2 and content[0] == content[-1] and content[0] in "\"'":
        content = content[1:-1].strip()
    elif streaming and content and content[0] in "\"'":
        content = content[1:].strip()
    return content


def _run_chat(*, model, messages, on_token=None, temperature=None, max_tokens=None):
    if on_token:
        raw_parts = []
        display_emitted = ""
        for chunk in llm_chat_stream(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if not chunk:
                continue
            raw_parts.append(chunk)
            display = sanitize_interviewer_display_text("".join(raw_parts), streaming=True)
            delta = display[len(display_emitted):]
            if delta:
                on_token(delta)
                display_emitted = display
        raw_full = "".join(raw_parts)
        return {
            "message": {"content": display_emitted},
            "raw_content": raw_full,
        }
    res = ollama_chat(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    raw_text = res["message"]["content"]
    return {
        "message": {"content": sanitize_interviewer_display_text(raw_text)},
        "raw_content": raw_text,
    }


def normalize_assessment_label(raw: str, allowed: set[str], default: str) -> str:
    text = (raw or "").strip().lower().strip("\"'")
    text = text.rstrip(".,!?;:")
    if text in allowed:
        return text
    tokens = re.sub(r"[^a-z0-9_]+", " ", text).split()
    for label in allowed:
        if label in tokens:
            return label
        label_words = label.replace("_", " ").split()
        if len(label_words) > 1 and all(word in tokens for word in label_words):
            return label
    return default


def log(func_name):
    if func_name.startswith("handle_"):
        color_code = (
            BLUE + BOLD if "intro" in func_name else
            GREEN + BOLD if "job" in func_name else
            CYAN + BOLD if "icebreaker" in func_name else
            "\033[35m" + BOLD if "followup" in func_name else
            "\033[33m" + BOLD if "resume" in func_name else
            "\033[96m" + BOLD if "custom" in func_name else
            "\033[91m" + BOLD if "candidate" in func_name else
            RED + BOLD
        )
    else:  # subfunctions like generate_ / assess_
        color_code = (
            BLUE if "intro" in func_name else
            GREEN if "job" in func_name else
            CYAN if "icebreaker" in func_name else
            "\033[35m" if "followup" in func_name else
            "\033[33m" if "resume" in func_name else
            "\033[96m" if "custom" in func_name else
            "\033[91m" if "candidate" in func_name else
            RED
        )

    print(f"{color_code}[Debug] called {func_name}{RESET}")


def _is_non_answer(text):
    normalized = re.sub(r"[^a-z0-9]+", " ", (text or "").strip().lower()).strip()
    if not normalized:
        return True
    if normalized in {
        "idk", "i dont know", "i do not know", "dont know", "not sure",
        "no idea", "nothing", "whatever", "skip", "pass", "na", "n a"
    }:
        return True
    return len(normalized.split()) <= 2 and normalized in {"no", "yes", "ok", "okay"}


def _is_substantive_response(text):
    normalized = re.sub(r"[^a-z0-9]+", " ", (text or "").strip().lower()).strip()
    if _is_non_answer(normalized):
        return False
    words = normalized.split()
    if len(words) >= 6:
        return True
    return any(
        keyword in normalized
        for keyword in (
            "engineer", "developer", "experience", "project", "worked",
            "built", "managed", "designed", "debug", "deploy", "python",
            "react", "aws", "database", "api", "hobby", "enjoy", "like"
        )
    )


# ===== BEGINING OF - INTRO FUNCTIONS USED =====


def _looks_like_self_intro(text: str) -> bool:
    """Heuristic: name/education/background signals that count as a real intro."""
    normalized = re.sub(r"[^a-z0-9]+", " ", (text or "").strip().lower()).strip()
    if not normalized or _is_non_answer(normalized):
        return False
    words = normalized.split()
    if len(words) < 5:
        return False

    has_name = any(
        phrase in normalized
        for phrase in ("my name is", "i am ", "i m ", "i'm ", "this is ")
    ) or normalized.startswith("i am") or normalized.startswith("im ")

    education_cues = (
        "btech", "b tech", "be ", "b e ", "bs ", "ms ", "mtech", "bachelor", "masters",
        "degree", "graduated", "graduate", "college", "university", "school",
        "major", "minor", "student", "studying", "studied", "ece", "cse", "cs ",
        "computer science", "engineering", "mit", "iit", "nit", "batch", "class of",
    )
    has_education = any(cue.strip() in normalized for cue in education_cues)

    background_cues = (
        "experience", "worked", "working", "internship", "intern", "years",
        "developer", "engineer", "background", "currently",
    )
    has_background = any(cue in normalized for cue in background_cues)

    # Name + education/background, or a longer intro with education/background alone.
    if has_name and (has_education or has_background):
        return True
    if has_education and len(words) >= 8:
        return True
    if has_background and len(words) >= 10:
        return True
    return False


def _conversation_has_sufficient_intro(conversation_history) -> bool:
    user_messages = [
        (item.get("content") or "")
        for item in conversation_history
        if item.get("role") == "user"
    ]
    return any(_looks_like_self_intro(message) for message in user_messages)


def generate_contextual_intro_reply(job_title, job_description, conversation_history, user_input, on_token=None):
    log("generate_contextual_intro_reply")

    prompt = f"""
You are an AI interviewer mid-introduction for the role of: {job_title}.

Job description (only use if they explicitly ask about the role):
{job_description}

Your only job in this stage is to help them introduce themselves.
- If they have not introduced themselves yet, ask briefly for a short intro (name, education, background).
- If they already shared an intro, acknowledge briefly in one short sentence and ask at most one light clarifying question — or simply encourage them to continue if needed.
- If they explicitly ask what the role involves, answer briefly in your own words (1–2 sentences). Do not volunteer a job explanation otherwise.
- Do NOT append any special tags or markers.

Rules:
- 1–2 well-formed sentences only.
- No headings, labels, or formatting.
- Do not restart with Welcome / Nice to meet you / Hi there.
- Never invent that they asked about the job when they did not.
    """

    messages = [{"role": "system", "content": prompt}]
    messages.extend(conversation_history)
    # handle_intro_stage already appends user_input to history — avoid a duplicate user turn.
    if not (
        conversation_history
        and conversation_history[-1].get("role") == "user"
        and (conversation_history[-1].get("content") or "").strip() == (user_input or "").strip()
    ):
        messages.append({"role": "user", "content": user_input})

    try:
        response = _run_chat(
            model="llama3",
            messages=messages,
            on_token=on_token,
            temperature=TEMP_REPLY,
        )
        return {"message": response["message"]["content"]}

    except Exception as e:
        print(f"[ERROR] contextual_intro_reply failed: {e}")
        if _is_substantive_response(user_input) or _looks_like_self_intro(user_input):
            return {"message": "Thanks for sharing that."}
        return {"message": "Could you tell me a bit about yourself?"}


def assess_intro_progress(conversation_history):
    log("assess_intro_progress")
    prompt = f"""
You are labeling whether the candidate has finished a basic self-introduction.

Conversation so far:
{json.dumps(conversation_history, indent=2)}

Return exactly one word:
- continue → they already shared a real intro (e.g. name + education, or education/background with enough detail)
- wait → only a greeting / tiny fragment so far, and they seem about to say more
- retry → trolling, gibberish, or clearly refusing to introduce themselves

Examples that MUST be continue:
- "My name is Neeraj. I did BTech in ECE at MIT Manipal and graduated in 2024."
- "I'm Priya, CS graduate from NIT, looking for backend roles."
- Name + college/degree even if they later say "no projects" or "no internships"

Examples that are wait:
- "hi"
- "hello"
- "sure"

Examples that are retry:
- "idk"
- "whatever"
- "asdfgh"

Important:
- Denying projects/internships after an intro is still continue (intro is done).
- Prefer continue when in doubt if any user turn already has name + education/background.
- Only one word. No explanation.
    """

    def _fallback_label() -> str:
        user_messages = [
            (item.get("content") or "")
            for item in conversation_history
            if item.get("role") == "user"
        ]
        if _conversation_has_sufficient_intro(conversation_history):
            return "continue"
        if any(_is_substantive_response(message) for message in user_messages):
            return "continue"
        if user_messages and _is_non_answer(user_messages[-1]):
            return "retry"
        return "wait"

    try:
        response = ollama_chat(
            model="llama3",
            messages=[{"role": "system", "content": prompt}],
            temperature=TEMP_EVAL,
        )
        raw = response["message"]["content"].strip()
        allowed = {"continue", "wait", "retry"}
        normalized = normalize_assessment_label(raw, allowed, "")
        # Heuristic override: never keep them stuck if a solid intro already happened.
        if _conversation_has_sufficient_intro(conversation_history):
            return "continue"
        if normalized in allowed:
            return normalized
        return _fallback_label()

    except Exception as e:
        print(f"[ERROR] assess_intro_progress failed: {e}")
        return _fallback_label()


# ===== END OF - INTRO FUNCTIONS USED =====

# ===== BEGINING OF - ICE BREAKER FUNCTIONS USED =====

def assess_icebreaker_response(user_response, question, conversation_history=None):
    log("assess_icebreaker_response")

    history = conversation_history or []
    system_prompt = """
You classify whether an icebreaker answer is enough to move on in a job interview.

Reply with exactly one word: valid or retry

Decision rule (keep the bar low):
- valid = the candidate gave any real personal content about themselves in response to the question: a like, dislike, preference, habit, interest, or honest “I don’t do X”. Spelling and grammar do not matter. Length does not matter.
- retry = only when there is no personal content to work with: empty, gibberish, or a pure shutdown with nothing about them (e.g. only “idk” / “whatever” / random characters).

Important:
- Judge ONLY the latest icebreaker question and latest answer.
- Earlier intro refusals must NOT push you to retry a good icebreaker answer.
- If the answer could reasonably count as personal engagement, choose valid.
- When unsure, choose valid.
""".strip()

    user_prompt = f"""
Latest icebreaker question: {question}
Latest candidate answer: {user_response}

Recent conversation (context only; do not over-weight older turns):
{json.dumps(history[-8:], indent=2)}

Your one-word label:
""".strip()

    try:
        response = ollama_chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMP_EVAL,
            max_tokens=16,
        )
        raw = response["message"]["content"]
        print(f"[DEBUG] Icebreaker assess raw → {raw!r}")
        allowed = {"valid", "retry"}
        # Prefer moving on if the model returns an unparseable label.
        return normalize_assessment_label(raw, allowed, "valid")
    except Exception as e:
        print(f"[ERROR] Icebreaker assessment failed: {e}")
        return "retry"


def generate_icebreaker_question(job_title, conversation_history=None, on_token=None, is_retry=False):
    log("generate_icebreaker_question")
    history = conversation_history or []
    retry_guidance = ""
    if is_retry:
        retry_guidance = """
This is a retry: the previous icebreaker answer was not usable.
Ask either:
- a short follow-up that helps them answer more concretely, OR
- a fresh icebreaker on a different light theme
Use the conversation history so you do not repeat the same question.
"""
    else:
        retry_guidance = """
This is the first icebreaker after their introduction.
Ask one new light personal question.
"""

    prompt = f"""
You are an AI interviewer mid-interview for the role of {job_title}.
The introduction stage is done. Stay in the icebreaker stage.

Conversation so far:
{json.dumps(history, indent=2)}

{retry_guidance}

Theme ideas (pick one; vary across turns):
- food / cooking
- music / movies / shows
- sports / fitness
- travel / places
- books / games
- pets / outdoors
- a simple preference (morning vs night, etc.)

Rules:
- Return ONLY the question text — one sentence.
- Do NOT greet or reopen the conversation (no Hi, Hello, Hey, Thanks, Welcome).
- Do NOT add transition filler before the question.
- Keep it simple, human, and non-technical — not studies or job skills.
- Do not repeat a question already asked in the conversation.
            """
    try:
        response = _run_chat(
            model="llama3",
            messages=[{"role": "system", "content": prompt}],
            on_token=on_token,
            temperature=TEMP_QUESTION,
        )
        return response["message"]["content"]

    except Exception as e:
        print(f"[ERROR] Icebreaker generation failed: {e}")
        return "What's something you enjoy doing in your free time?"
        
# ===== END OF - ICE BREAKER FUNCTIONS USED =====
    

# ===== BEGGINING OF - INTRO FOLLOW-UP FUNCTIONS USED =====

def assess_followup_response(question, user_response, conversation_history=None):
    log("assess_followup_response")

    history = conversation_history or []
    system_prompt = """
You classify whether a candidate's answer is good enough to leave the intro follow-up stage.

Reply with exactly one word: strong or weak

How to read the question:
- The interviewer message may include small talk or transitions before the real ask.
- Judge against the main ask only (the actual question being posed).

Decision rule (be fair to informal answers):
- strong = the candidate engages the main topic with some real personal/professional content: a project, role, experience, motivation, or concrete detail. Typos, informal wording, and partial coverage are fine. They do NOT need to hit every keyword in the question.
- weak = almost no usable signal for that ask: blank, "no idea" / "idk", pure refusal, gibberish, or an answer that is clearly about something else with no connection to the ask.

Examples of intent (do not overfit wording):
- Asked about HTTP APIs / backend work, and they describe a web/API project they built → strong
- Asked about Python + Postgres, and they describe a Python project (even if Postgres is missing) → strong if it is still clearly about relevant experience
- Asked a technical follow-up and they say "no idea" → weak

When the answer is roughly on-topic and shares something real, choose strong.
When unsure, prefer strong if there is any on-topic personal/professional content; choose weak only if the ask was basically unanswered.
""".strip()

    user_prompt = f"""
Interviewer message: {question}
Candidate answer: {user_response}

Recent conversation (context only):
{json.dumps(history[-10:], indent=2)}

Your one-word label:
""".strip()

    try:
        response = ollama_chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMP_EVAL,
            max_tokens=16,
        )
        result = response["message"]["content"].strip()
        print(f"[DEBUG] Follow-up assess raw → {result!r}")
        allowed = {"strong", "weak"}
        return normalize_assessment_label(result, allowed, "strong")
    except Exception as e:
        print(f"[ERROR] assess_followup_response failed: {e}")
        return "weak"



def generate_dynamic_question(job_title, job_description, conversation_history, on_token=None, is_retry=False):
    log("generate_dynamic_question")
    retry_guidance = ""
    if is_retry:
        retry_guidance = """
The candidate's last answer did not adequately address the previous follow-up (off-topic, vague, or missing the ask).
Ask ONE tighter follow-up that:
- redirects them back to what was missing, OR
- digs into a useful gap in what they just said while still staying on the prior topic
Use the conversation history. Do not repeat the previous question verbatim.
"""
    else:
        retry_guidance = """
Ask ONE follow-up to learn more about their background, experience, motivation, or role fit.
"""

    messages = [
        {
            "role": "system",
            "content": f"""
You are an AI interviewer mid-interview for the role of: {job_title}.
You are in the intro follow-up stage — gather useful signal before resume questions.

Job Description:
{job_description}

{retry_guidance}

Rules:
- Return ONLY the question text — one concise sentence.
- Do NOT greet. Do NOT thank them. Do NOT comment on the icebreaker (food, music, hobbies, etc.).
- Do NOT add filler like "That's interesting", "Burgers are a classic", or "Moving back to your experience".
- Do not repeat something already fully answered.
- Light experience / project / motivation questions are allowed; keep it conversational, not a deep technical grill.

Only the question.
            """
        },
        *conversation_history
    ]

    try:
        response = _run_chat(
            model="llama3",
            messages=messages,
            on_token=on_token,
            temperature=TEMP_QUESTION,
        )
        return response["message"]["content"]

    except Exception as e:
        print(f"[ERROR] generate_dynamic_question failed: {e}")
        return "Can you tell me more about your motivation for applying to this role?"


# ===== END OF - INTRO FOLLOW-UP FUNCTIONS USED =====


# ===== BEGGINING OF - RESUME DISCUSSION FUNCTIONS USED =====

def evaluate_resume_response(question, response):
    log("evaluate_resume_response")
    system_prompt = """
You classify a candidate's answer to a resume / experience interview question.

Reply with exactly one word:
strong | weak | confused | off_topic

Label meanings:
- strong = on-topic enough, with real substance: ownership, what they built/did, a concrete example, technology, or outcome. Informal wording and typos are fine. They do not need a perfect metric or to match the question wording literally.
- weak = related to the question but thin: vague, "no idea"/"idk", missing ownership/example, or too shallow to accept yet.
- confused = they misunderstood what was asked (answer the wrong kind of thing while still trying).
- off_topic = unrelated personal chatter, jokes, or content with no connection to the question or role experience.

Important:
- Adjacent backend/engineering detail that still answers the spirit of the question is NOT off_topic.
- Prefer strong when there is clear on-topic professional content.
- Prefer weak over confused/off_topic when they attempted the topic but lacked depth.
- Prefer off_topic only for clearly unrelated answers.
""".strip()

    user_prompt = f"""
Question: {question}
Candidate answer: {response}

Your one-word label:
""".strip()

    try:
        res = ollama_chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMP_EVAL,
            max_tokens=16,
        )
        raw = res["message"]["content"].strip()
        print(f"[DEBUG] Resume evaluate raw → {raw!r}")
        allowed = {"strong", "weak", "confused", "off_topic"}
        default = "weak" if not _is_substantive_response(response) else "strong"
        return normalize_assessment_label(raw, allowed, default)

    except Exception as e:
        print(f"[ERROR] evaluate_resume_response failed: {e}")
        return "weak" if not _is_substantive_response(response) else "strong"

def generate_followup_question(original_question, weak_response, on_token=None):
    log("generate_followup_question")
    prompt = f"""
You are an AI interviewer mid-interview. The candidate's last answer was weak or incomplete.
Ask one short follow-up that continues the same thread — do not restart the conversation.

Original question: "{original_question}"
Candidate answer: "{weak_response}"

Rules:
- Return ONLY the follow-up question — one sentence.
- Do NOT greet or reopen the chat. Never start with Hello, Hi, Hey, Hi there, Thanks, or Welcome.
- Do NOT say "I understand" / "No worries" as a long preamble; go straight to the question.
- Probe one concrete gap (ownership, example, metric, outcome, or technology) related to the original question.
    """
    try:
        res = _run_chat(
            model="llama3",
            messages=[{"role": "system", "content": prompt}],
            on_token=on_token,
            temperature=TEMP_QUESTION,
        )
        return res["message"]["content"]

    except:
        return "Could you elaborate a bit more on that?"

# ===== END OF - RESUME DISCUSSION FUNCTIONS USED =====

# ===== BEGINING OF - FUCNTIONS USED FOR CUSTOM QUESTIONS ====== 

def evaluate_custom_response(question, response):
    log("evaluate_custom_response")
    system_prompt = """
You classify a candidate's answer to a custom technical or behavioral interview question.

Reply with exactly one word:
clear | weak | confused | no_answer | off_topic

Label meanings:
- clear = relevant and useful: explains the idea with enough confidence/detail to move on (informal wording OK).
- weak = on-topic but vague or missing important detail.
- confused = misunderstands the question.
- no_answer = explicitly doesn't know / won't answer ("idk", "not sure", "no idea").
- off_topic = unrelated to the question.

Important:
- Prefer clear when the answer addresses the ask with real content.
- Prefer weak over confused/off_topic when they tried the topic but stayed shallow.
- Do not mark a relevant technical answer off_topic just because it is imperfect or incomplete.
""".strip()

    user_prompt = f"""
Question: {question}
Candidate answer: {response}

Your one-word label:
""".strip()

    try:
        result = ollama_chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMP_EVAL,
            max_tokens=16,
        )
        raw = result["message"]["content"].strip()
        print(f"[DEBUG] Custom evaluate raw → {raw!r}")
        allowed = {"clear", "weak", "confused", "no_answer", "off_topic"}
        default = "clear" if _is_substantive_response(response) else "confused"
        return normalize_assessment_label(raw, allowed, default)

    except Exception as e:
        print(f"[ERROR] evaluate_custom_response failed: {e}")
        return "clear" if _is_substantive_response(response) else "confused"

def generate_custom_followup(question, last_response, on_token=None):
    log("generate_custom_followup")
    prompt = f"""
You are an AI interviewer mid-interview. Ask one short follow-up that continues the same thread.

Original question: "{question}"
Candidate answer: "{last_response}"

Rules:
- Return ONLY the follow-up question — one sentence.
- Do NOT greet or reopen the chat. Never start with Hello, Hi, Hey, Hi there, Thanks, or Welcome.
- No preamble — go straight to the question.
- Focus on clarifying their conceptual grasp or getting a concrete example.
    """
    try:
        result = _run_chat(
            model="llama3",
            messages=[{"role": "system", "content": prompt}],
            on_token=on_token,
            temperature=TEMP_QUESTION,
        )
        return result["message"]["content"]

    except Exception:
        return "Could you clarify your thinking or give an example?"

def generate_model_answer(question, on_token=None):
    log("generate_model_answer")
    prompt = f"""
        You are an AI interviewer.

        The candidate struggled to answer:
        "{question}"

        Give a **short** model answer in 2–3 concise sentences:
        - Clearly explain the key concept.
        - If helpful, include a quick example.
        - End with "That's how you could approach it."

        Keep it crisp and under 50 words.
        Only return the answer — no explanation or extra text.
        """
    try:
        result = _run_chat(
            model="llama3",
            messages=[{"role": "system", "content": prompt}],
            on_token=on_token,
            temperature=TEMP_REPLY,
        )
        return result["message"]["content"]

    except Exception as e:
        print(f"[ERROR] generate_model_answer failed: {e}")
        return "Tuples are immutable; lists are not. Use tuples when values shouldn't change. That's how you could approach it."

# ===== END OF - FUCNTIONS USED FOR CUSTOM QUESTIONS ====== 

# ===== BEGINING OF - FUCNTIONS USED FOR END OF INTERVIEW CANDIDATE QUESTION====== 

def _parse_json_object(response_text: str) -> dict:
    text = (response_text or "").strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        parsed = json.loads(text[start:end])
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("No JSON object found in response")


_CANDIDATE_QNA_INTENTS = {
    "decline",
    "ask_question",
    "wants_to_ask",
    "greeting_or_chitchat",
    "unclear",
}


def run_candidate_qna_turn(
    user_input,
    conversation_history,
    evaluation_log,
    job_title,
    job_description="",
    questions_remaining=None,
    last_chance=False,
    on_token=None,
):
    """
    One structured LLM call for candidate Q&A wrap-up.

    Returns:
      intent: decline | ask_question | wants_to_ask | greeting_or_chitchat | unclear
      reply: interviewer spoken line
      should_count_as_question: whether this turn used one of the soft question slots
      ready_to_end: LLM hint that they are done (code still owns lock/end)
    """
    log("run_candidate_qna_turn")
    remaining = questions_remaining
    system_prompt = f"""
You are the interviewer wrapping up a job interview for: {job_title}.

Classify the candidate's latest message and write your spoken reply in ONE JSON object.

Return ONLY valid JSON (no markdown, no extra text):
{{
  "intent": "decline" | "ask_question" | "wants_to_ask" | "greeting_or_chitchat" | "unclear",
  "reply": "your spoken reply",
  "should_count_as_question": true or false,
  "ready_to_end": true or false
}}

Intent meanings:
- decline: they do not want to ask more / are finished (e.g. no, I'm good, that's all).
- ask_question: they asked a real question (role, company, team, next steps, timeline, OR how they did / feedback).
- wants_to_ask: they want to ask but have not asked yet (e.g. yes, I have one, one more thing) — and it is NOT already a feedback ask.
- greeting_or_chitchat: greeting or small talk with no question (e.g. hi, hello, thanks).
- unclear: cannot tell; keep the wrap-up open.

Important classification:
- “How did I do?”, “any feedback?”, “how was my interview?”, “did I do well?” → intent ask_question (never unclear, never wants_to_ask).
- A bare “yes” after you already asked them to clarify a feedback request → still ask_question (they confirmed they want interview feedback).

Field rules:
- should_count_as_question = true ONLY for intent ask_question.
- ready_to_end = true ONLY for intent decline.
- For greeting_or_chitchat / unclear / wants_to_ask: ready_to_end must be false.

Reply rules by intent:
- decline: brief thanks + nudge to press End Interview for feedback.
- ask_question about the role/company/team/next steps/timeline:
  answer helpfully in 2–3 short sentences using the job title/JD/conversation.
  Never deflect normal role/job questions.
  Off-topic trivia / personal reverse-interview → polite redirect to role topics.
- ask_question about performance / “how did I do” / feedback / scores:
  Do NOT give live scores, strengths, weaknesses, or critique.
  Do NOT ask them to clarify what kind of feedback they want.
  Reply briefly that they can view their summary and scores after they press End Interview,
  then invite any other questions about the role or next steps.
  Example tone: “You’ll be able to view your scores and a full summary after you press End Interview. Any other questions about the role or next steps?”
- wants_to_ask: invite them to ask (e.g. “Sure — what’s your question?”).
- greeting_or_chitchat / unclear: briefly acknowledge and re-ask if they have questions about the role.

Tone: professional, warm, neutral. No “great question” / “thanks for asking” / “I'm glad you asked”. No labels outside JSON.
""".strip()

    if last_chance or (isinstance(remaining, int) and remaining <= 1):
        system_prompt += """

Context: they are near the end of the allowed candidate questions.
If intent is ask_question and it is NOT a feedback/how-did-I-do ask, you may close the answer warmly in one short extra line.
For feedback asks, still only defer to End Interview — do not give live evaluation.
""".rstrip()

    recent_history = (conversation_history or [])[-12:]
    user_prompt = f"""
Candidate's latest message:
{user_input}

Job description (context):
{(job_description or "")[:2500]}

Questions remaining (soft limit): {remaining if remaining is not None else "unknown"}

Recent conversation:
{json.dumps(recent_history, indent=2)}

Note: Do not use performance notes to score the candidate live. Feedback/scores are only after End Interview.
""".strip()

    fallback = {
        "intent": "unclear",
        "reply": "Do you have any questions about the role before we wrap up?",
        "should_count_as_question": False,
        "ready_to_end": False,
    }

    try:
        result = ollama_chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMP_STRUCTURED,
            max_tokens=400,
        )
        raw = result["message"]["content"].strip()
        parsed = _parse_json_object(raw)

        intent = normalize_assessment_label(
            str(parsed.get("intent", "")),
            _CANDIDATE_QNA_INTENTS,
            "unclear",
        )
        reply = sanitize_interviewer_display_text(str(parsed.get("reply") or "").strip())
        if not reply:
            reply = fallback["reply"]

        should_count = bool(parsed.get("should_count_as_question")) and intent == "ask_question"
        ready_to_end = bool(parsed.get("ready_to_end")) and intent == "decline"

        # Enforce intent/field consistency in code.
        if intent == "ask_question":
            should_count = True
            ready_to_end = False
        elif intent == "decline":
            should_count = False
            ready_to_end = True
            if "end interview" not in reply.lower():
                reply = (
                    f"{reply.rstrip()} "
                    "Please press the End Interview button for your feedback."
                ).strip()
        else:
            should_count = False
            ready_to_end = False

        if on_token and reply:
            on_token(reply)

        return {
            "intent": intent,
            "reply": reply,
            "should_count_as_question": should_count,
            "ready_to_end": ready_to_end,
        }

    except Exception as e:
        print(f"[ERROR] run_candidate_qna_turn failed: {e}")
        if on_token and fallback["reply"]:
            on_token(fallback["reply"])
        return fallback


# Keep thin aliases for any older call sites / tests.
def assess_candidate_has_question(user_input):
    result = run_candidate_qna_turn(
        user_input=user_input,
        conversation_history=[],
        evaluation_log=[],
        job_title="this role",
    )
    return "no" if result["intent"] == "decline" else "yes"


def generate_candidate_qna_response(
    user_question,
    conversation_history,
    evaluation_log,
    job_title,
    last_chance=False,
    on_token=None,
):
    result = run_candidate_qna_turn(
        user_input=user_question,
        conversation_history=conversation_history,
        evaluation_log=evaluation_log,
        job_title=job_title,
        last_chance=last_chance,
        on_token=on_token,
    )
    return result["reply"]



# ===== END OF - FUCNTIONS USED FOR END OF INTERVIEW CANDIDATE QUESTION====== 

# ===== BEGINING OF - FUCNTIONS USED FOR EVALUATING CANDIDATE QUESTION====== 

def analyze_individual_responses(evaluation_log, model="llama3"):
    log("analyze_individual_responses")
    analyzed = []

    for item in evaluation_log:
        q = item["question"]
        a = item["response"]

        prompt = f"""
            Evaluate the following interview response:

            Question: "{q}"
            Candidate's Answer: "{a}"

            Provide detailed evaluation metrics in JSON format.
            For each metric, give a numeric score from 0 to 10, plus an emotion label.

            Metrics to include:
            1. knowledge_depth – understanding of the question
            2. communication_clarity – organization and flow of ideas
            3. confidence_tone – tone of communication (e.g., confident, nervous, neutral)
            4. reasoning_ability – logical reasoning or problem-solving shown
            5. relevance_to_question – how well it stays on-topic
            6. motivation_indicator – enthusiasm, passion, or drive reflected in response

            Respond ONLY in valid JSON:
            {{
            "knowledge_depth": 0–10,
            "communication_clarity": 0–10,
            "confidence_tone": 0–10,
            "reasoning_ability": 0–10,
            "relevance_to_question": 0–10,
            "motivation_indicator": 0–10,
            "emotion": "label"
            }}
            """

        try:
            result = ollama_chat(
                model=model,
                messages=[{"role": "system", "content": prompt}],
                temperature=TEMP_STRUCTURED,
            )
            response_text = result["message"]["content"].strip()
            
            # Try to extract JSON from the response
            try:
                # First, try to parse the whole response
                parsed = json.loads(response_text)
            except json.JSONDecodeError:
                # If that fails, try to extract JSON from the response
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start != -1 and json_end != 0:
                    json_text = response_text[json_start:json_end]
                    parsed = json.loads(json_text)
                else:
                    # If no JSON found, use default values
                    raise Exception("No JSON found in response")
            
            item["knowledge_depth"] = parsed.get("knowledge_depth", 5)
            item["communication_clarity"] = parsed.get("communication_clarity", 5)
            item["confidence_tone"] = parsed.get("confidence_tone", 5)
            item["reasoning_ability"] = parsed.get("reasoning_ability", 5)
            item["relevance_to_question"] = parsed.get("relevance_to_question", 5)
            item["motivation_indicator"] = parsed.get("motivation_indicator", 5)
            item["emotion"] = parsed.get("emotion", "neutral")

            
        except Exception as e:
            print(f"[ERROR] analyze_individual_responses failed for question '{q[:50]}...': {e}")
            print(f"[DEBUG] Response text: {response_text if 'response_text' in locals() else 'No response'}")

            # Assign safe default values so JSON parsing errors don't break the flow
            item["knowledge_depth"] = 5
            item["communication_clarity"] = 5
            item["confidence_tone"] = 5
            item["reasoning_ability"] = 5
            item["relevance_to_question"] = 5
            item["motivation_indicator"] = 5
            item["emotion"] = "unknown"
            item["overall_score"] = 5.0  # Optional overall average placeholder


        analyzed.append(item)

    return analyzed


def generate_final_summary_review(job_title, conversation_history, analyzed_log, model="llama3"):
    log("generate_final_summary_review")

    def build_deterministic_fallback():
        overall_rating = round(avg_overall_rating, 1)
        if overall_rating >= 7.5:
            final_label = "strong"
        elif overall_rating >= 5.5:
            final_label = "average"
        else:
            final_label = "weak"

        summary_parts = [
            f"The candidate showed {final_label} overall alignment for the {job_title} role.",
            f"Overall performance averaged {overall_rating:.1f}/10, with knowledge depth at {avg_knowledge_depth:.1f}/10 and communication clarity at {avg_communication_clarity:.1f}/10.",
            f"The dominant emotional tone was {overall_emotion}, with reasoning ability at {avg_reasoning_ability:.1f}/10 and relevance at {avg_relevance_to_question:.1f}/10.",
        ]
        if strong_responses:
            summary_parts.append(f"There were {strong_responses} stronger responses that showed useful baseline capability.")
        if weak_responses:
            summary_parts.append(f"There were {weak_responses} weaker responses where the candidate needed more depth or specificity.")
        summary = " ".join(summary_parts).strip()
        if not summary.endswith(final_label):
            summary = f"{summary} {final_label}"

        strengths = []
        if avg_knowledge_depth >= 6:
            strengths.append("Demonstrated workable baseline knowledge for several interview topics.")
        if avg_communication_clarity >= 6:
            strengths.append("Communicated ideas with reasonable clarity in parts of the interview.")
        if avg_relevance_to_question >= 6:
            strengths.append("Stayed relevant to the questions and generally addressed the intent of prompts.")
        if avg_motivation_indicator >= 6:
            strengths.append("Showed signs of motivation and interest in the role.")
        if not strengths:
            strengths.append("Completed the interview flow and provided enough responses for a baseline evaluation.")
            strengths.append("Showed willingness to engage with the interview process.")

        improvements = []
        if avg_knowledge_depth < 6:
            improvements.append("Improve technical depth by preparing clearer examples, concepts, and project details.")
        if avg_communication_clarity < 6:
            improvements.append("Use more structured answers with context, action, and outcome to improve clarity.")
        if avg_confidence_tone < 6 or nervous_responses > 0 or unsure_responses > 0:
            improvements.append("Practice delivery and mock interviews to improve confidence and reduce hesitation.")
        if avg_reasoning_ability < 6:
            improvements.append("Explain the reasoning behind decisions more explicitly instead of giving short conclusions.")
        if avg_relevance_to_question < 6:
            improvements.append("Answer the exact question first, then support it with a concrete example.")
        if not improvements:
            improvements.append("Continue sharpening role-specific examples to make strong answers more consistent.")

        return {
            "summary": f"{summary} (Overall Rating: {overall_rating:.1f}/10)",
            "key_strengths": "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(strengths[:8])),
            "improvement_areas": "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(improvements[:8])),
            "overall_rating": overall_rating,
            "metrics": {
                "overall_rating": overall_rating,
                "knowledge_depth": round(avg_knowledge_depth, 1),
                "communication_clarity": round(avg_communication_clarity, 1),
                "confidence_tone": round(avg_confidence_tone, 1),
                "reasoning_ability": round(avg_reasoning_ability, 1),
                "relevance_to_question": round(avg_relevance_to_question, 1),
                "motivation_indicator": round(avg_motivation_indicator, 1),
                "overall_emotion": overall_emotion,
                "overall_emotion_summary": f"The candidate's overall tone was {overall_emotion}.",
            }
        }


    # Calculate overall statistics for context using new detailed metrics
    total_responses = len(analyzed_log)
    if total_responses > 0:
        avg_knowledge_depth = sum(item.get('knowledge_depth', 5) for item in analyzed_log) / total_responses
        avg_communication_clarity = sum(item.get('communication_clarity', 5) for item in analyzed_log) / total_responses
        avg_confidence_tone = sum(item.get('confidence_tone', 5) for item in analyzed_log) / total_responses
        avg_reasoning_ability = sum(item.get('reasoning_ability', 5) for item in analyzed_log) / total_responses
        avg_relevance_to_question = sum(item.get('relevance_to_question', 5) for item in analyzed_log) / total_responses
        avg_motivation_indicator = sum(item.get('motivation_indicator', 5) for item in analyzed_log) / total_responses
        avg_overall_rating = (
            avg_knowledge_depth +
            avg_communication_clarity +
            avg_confidence_tone +
            avg_reasoning_ability +
            avg_relevance_to_question +
            avg_motivation_indicator
        ) / 6

        weak_responses = sum(1 for item in analyzed_log if item.get('evaluation') in ['weak', 'confused'])
        strong_responses = sum(1 for item in analyzed_log if item.get('evaluation') in ['strong', 'good'])
        nervous_responses = sum(1 for item in analyzed_log if item.get('emotion') == 'nervous')
        unsure_responses = sum(1 for item in analyzed_log if item.get('emotion') == 'unsure')
        # === Derive overall emotion across all responses ===
        emotion_counts = {}
        for item in analyzed_log:
            emotion = item.get("emotion", "neutral").lower()
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

        # Pick the most frequent emotion
        overall_emotion = max(emotion_counts, key=emotion_counts.get) if emotion_counts else "neutral"

    else:
        avg_knowledge_depth = avg_communication_clarity = avg_confidence_tone = 5
        avg_reasoning_ability = avg_relevance_to_question = avg_motivation_indicator = 5
        avg_overall_rating = 5
        weak_responses = strong_responses = nervous_responses = unsure_responses = 0
        overall_emotion = "neutral"  # ✅ ADD THIS LINE - Initialize overall_emotion for empty log case


    prompt = f"""
    You are an expert interview evaluator. Based on the following interaction, provide a comprehensive evaluation:

    Job Title: {job_title}

    Here is the full conversation:
    {json.dumps(conversation_history, indent=2)}

    And here is the evaluated log:
    {json.dumps(analyzed_log, indent=2)}

    EVALUATION STATISTICS:
    - Total Responses: {total_responses}
    - Overall Dominant Emotion: {overall_emotion.capitalize()}
    - Avg Knowledge Depth: {avg_knowledge_depth:.1f}/10
    - Avg Communication Clarity: {avg_communication_clarity:.1f}/10
    - Avg Confidence & Tone: {avg_confidence_tone:.1f}/10
    - Avg Reasoning Ability: {avg_reasoning_ability:.1f}/10
    - Avg Relevance to Question: {avg_relevance_to_question:.1f}/10
    - Avg Motivation Indicator: {avg_motivation_indicator:.1f}/10
    - Weak Responses: {weak_responses}
    - Strong Responses: {strong_responses}
    - Nervous Responses: {nervous_responses}
    - Unsure Responses: {unsure_responses}

    
    Please provide a comprehensive evaluation in JSON format with four sections:

    1. SUMMARY: Write a short 4–5 sentence summary evaluating the candidate's overall fit for this job. 
    - Consider knowledge and clarity across questions
    - Consider emotional tone (confidence, nervousness, etc.)
    - Consider communication effectiveness
    - The summary **must explicitly end with one of these exact words, in lowercase: "strong", "average", or "weak". 
        This is mandatory, as it will be programmatically extracted.**


    2. KEY STRENGTHS: List 6–8 **specific, evidence-based strengths** the candidate demonstrated. 
        - Only include strengths if they are clearly supported by the evaluation log 
            (e.g., knowledge rating ≥ 6/10, "strong" responses, confident/enthusiastic tone, or concrete examples mentioned). 
        - Where possible, link the strength to how it can be leveraged to improve weaker areas 
            (e.g., “Strong communication in casual answers — could apply this clarity to technical explanations”). 
        - If no strong evidence exists, explicitly state: 
            "No significant strengths were demonstrated due to vague or non-specific responses."
        - Avoid generic filler like "professional demeanor" unless clearly evident.

    3. IMPROVEMENT AREAS: List 6–8 **concrete, actionable improvement areas**. 
        - Tie each point directly to weaknesses in the evaluation log 
            (e.g., ratings < 5/10, multiple "weak/confused" responses, nervous/unsure emotional tone). 
        - Provide specific guidance on how to improve (e.g., “Instead of one-word answers, provide examples of projects to show depth”). 
        - If performance was consistently weak, you may state: 
            "The candidate should significantly improve technical depth, communication clarity, and confidence before reapplying."

    4. OVERALL EMOTION SUMMARY – a **one-sentence description** of the candidate’s overall emotional tone throughout the interview.  
        Example: "Started nervous but became confident by the end" or "Consistently calm and professional."  
        Return this line in the JSON as **"overall_emotion_summary"**.

    Return your response strictly as a single valid JSON object, with no text, comments, or explanations before or after it. 

    JSON format:
    {{
        "summary": "2–3 sentence summary here",
        "key_strengths": "1. [Specific strength 1]\\n2. [Specific strength 2]\\n3. [Specific strength 3]",
        "improvement_areas": "1. [Specific area 1]\\n2. [Specific area 2]\\n3. [Specific area 3]",
        "overall_rating": {avg_overall_rating:.1f},
        "overall_emotion_summary": "Short sentence describing emotional tone, e.g., 'Started nervous but became confident by the end.'"
    }}

    Be specific, constructive, and relevant to the {job_title} position. Base your analysis on the actual conversation and evaluation data provided.
    """

    parsed_response = {
        "summary": "Interview completed. Detailed AI summary was unavailable, so a fallback summary was generated.",
        "key_strengths": "1. Completed the interview flow and answered multiple questions.\n2. Provided enough conversation data for a baseline evaluation.",
        "improvement_areas": "1. Improve depth and specificity in answers.\n2. Practice confidence, clarity, and structured examples before the next interview.",
        "overall_rating": avg_overall_rating,
        "overall_emotion_summary": "Emotion summary not generated",
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            result = ollama_chat(
                model=model,
                messages=[{"role": "system", "content": prompt}],
                temperature=TEMP_STRUCTURED,
            )
            response_text = result["message"]["content"].strip()

            # Try to extract JSON
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                json_text = response_text[json_start:json_end]
                json_text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_text)
                parsed_response = json.loads(json_text)
            else:
                parsed_response = json.loads(response_text)

            # ✅ Success → return with rating in summary
            parsed_rating = parsed_response.get('overall_rating', avg_overall_rating)
            try:
                parsed_rating = float(parsed_rating)
            except Exception:
                parsed_rating = avg_overall_rating
            return {
                'summary': parsed_response.get('summary', '') + f" (Overall Rating: {parsed_rating:.1f}/10)",
                'key_strengths': parsed_response.get('key_strengths', ''),
                'improvement_areas': parsed_response.get('improvement_areas', ''),
                'overall_rating': parsed_rating,
                'metrics': {
                    "overall_rating": round(parsed_rating, 1),
                    "knowledge_depth": round(avg_knowledge_depth, 1),
                    "communication_clarity": round(avg_communication_clarity, 1),
                    "confidence_tone": round(avg_confidence_tone, 1),
                    "reasoning_ability": round(avg_reasoning_ability, 1),
                    "relevance_to_question": round(avg_relevance_to_question, 1),
                    "motivation_indicator": round(avg_motivation_indicator, 1),
                    "overall_emotion": overall_emotion,
                    "overall_emotion_summary": parsed_response.get("overall_emotion_summary", "Emotion summary not generated")
                }
            }

        except Exception as e:
            print(f"[WARN] Attempt {attempt+1}/{max_retries} failed: {e}")
            if "Failed to connect to Ollama" in str(e):
                return build_deterministic_fallback()
            if attempt < max_retries - 1:
                continue  # 🔁 retry again
            else:
                print("[ERROR] All retries failed")

    # === Fallback if all retries fail ===
    return build_deterministic_fallback()
