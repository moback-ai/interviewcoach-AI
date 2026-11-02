"""Direct question generation: raw resume + JD -> plan and questions -> review pass.

Replaces the dossier -> per-type prompts path for core mode. The writer sees the candidate's
full resume text and the JD, plans coverage first, then a second call reviews and fixes the set.
"""
from __future__ import annotations

import json

from INTERVIEW.generation_utils import (
    _parse_llm_json_object,
    extract_json_array,
    try_ollama_chat,
)

DIRECT_QUESTION_MAX_TOKENS = 4096
DIRECT_QUESTION_TEMPERATURE = 0.4
DIRECT_REVIEW_TEMPERATURE = 0.2
DIRECT_MAX_ATTEMPTS = 3
RESUME_CHARS_MAX = 14000
JD_CHARS_MAX = 7000

_WEIGHTS = {"beginner": 1, "medium": 3, "hard": 5}
_LEVELS = ("beginner", "medium", "hard")


def _clip(text, limit):
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit]


def _style_rules() -> str:
    return """QUESTION RULES
- Write the way a good interviewer speaks: natural, grammatical English a person could read aloud.
- Fit the role's field. Ask what a hiring manager for THIS job title would ask, using the vocabulary of that
  field (engineering, analytics, sales, marketing, finance, operations, design, ...). Do not bring in
  tools, methods or examples from another field.
- One subject per question: its parts must all concern the same topic, never two unrelated tools or methods.
- Every question has a checkable answer: a named feature, setting, method, framework, metric, formula,
  technique, trade-off or diagnostic step that a strong candidate in this field would state.
  Never ask only "what drove your decision".
- Shape by difficulty:
  beginner: a DIRECT question on a skill, tool or method named in the resume or JD, the way an interviewer
    checks fundamentals when they see it listed. Examples of the shape (other fields differ):
    engineering "Explain REST and the difference between PUT and PATCH"; analytics "What is the difference
    between an inner and a left join, and when does each change a total?"; sales "How do you qualify a lead
    with BANT, and what does each letter tell you?". 15-40 words, no invented scenario, and it must ask for
    understanding (how it works, the difference, when to use which), not a one-keyword lookup. A question
    about the candidate's own project is never beginner; label it medium or hard.
  medium: mix direct "explain how X works / how would you structure X" questions with short scenarios or
    "walk me through how you would..." questions, 30-60 words, with at most one connected follow-up part
    and no checklist of five dimensions.
  hard: starts from a concrete situation with real constraints (scale, failure, budget, deadline, conflicting
    requirements) and asks for a design, diagnosis, plan or trade-off, at most 60 words and 2-3 linked parts,
    whose answer needs several linked decisions. Not a single-fact answer, not a "how do A, B and C support
    D" knowledge question, and not a list of four or five deliverables.
- Wording: each sentence needs a sensible subject and verb. Do not write "let/allow <someone's question or
  thing> retrieve/do ..." (write "help retrieve ... for <someone's question>"). Keep modifiers next to what they
  modify, say "a query that contains both X and Y" rather than "a query containing X plus Y", and split a
  long setup into two short sentences instead of one run-on.
- Anchor at least a third of all questions in the candidate's own work: name their real project or employer in a
  short clause ("In your work at <employer>, ..." or "On the <project>, ...") and ask a substantive question
  about it. Mention the project at most once per question, never as a possessive or modifier. Never invent
  incidents, failures, numbers or outcomes in their past work: use only facts stated in the resume; invented
  numbers are fine only in hypothetical scenarios. Never ask the candidate to choose, pick or name a project
  or past work ("Choose a project you worked on and name it"): either name it yourself from the resume, or,
  if the resume names no project for that topic, ask the question about the topic directly.
- Stay inside the job title's own discipline. A skill the candidate lacks may appear in at most one
  hard question, phrased as "how would you approach", never as something they already did.
- If the JD asks for practice-level skills (for example process design, quality standards, stakeholder
  management, leading a team), one or two questions may cover them; otherwise stay on the role's core skills.
- Vary the shape across the set: at most half the questions may be scenarios; at least a third should be
  direct questions about a named skill, tool or method. If a core skill of this role appears in the resume or
  JD, ask about it directly at least once instead of only through scenarios.
- No one-word definitions, no repeated openers, no two questions on the same concept.
  At most one in three questions may start with "Which ... would you ..., and why?"."""


_DEFAULT_MIX = """Spread them roughly in thirds across (a) the candidate's own work, naming the project and asking a
   substantive question about it, (b) a core topic from their work, asked about the topic itself, and
   (c) JD requirements or tools not covered by (a) or (b)."""


def mix_instruction(mode, total, resume_pct=50, jd_pct=50, blend_pct_resume=50, blend_pct_jd=50):
    """Source-mix guidance for the writer. core keeps the default thirds."""
    total = max(0, int(total or 0))
    if mode == "blend":
        rn = round(total * (blend_pct_resume or 0) / 100)
        return (
            f"Blend the resume and the JD inside each question wherever possible. Of the {total} questions, "
            f"about {rn} should lean on the candidate's own work or topics while tying to a JD requirement, and "
            f"about {total - rn} should lead with a JD requirement while connecting it to something in their "
            f"background (a {blend_pct_resume}% resume / {blend_pct_jd}% JD weighting)."
        )
    if mode == "split":
        rn = round(total * (resume_pct or 0) / 100)
        return (
            f"Split by source. Exactly {rn} questions come ONLY from the candidate's resume (their own work or a "
            f"core topic in it; source work or topic) and exactly {total - rn} come ONLY from JD requirements "
            f"(source jd). JD-only questions must not mention the candidate's projects or employers."
        )
    if mode == "hybrid":
        blend_n = round(total * 0.4)
        rest = total - blend_n
        rn = round(rest * (resume_pct or 0) / 100)
        return (
            f"Use three buckets. {rn} questions come ONLY from the candidate's resume (source work or topic), "
            f"{rest - rn} come ONLY from JD requirements (source jd, no mention of their projects), and "
            f"{blend_n} blend both: they lean on the candidate's work and tie it to a JD requirement."
        )
    return _DEFAULT_MIX


def _build_plan_prompt(job_title, resume_text, job_description, counts, exclude, mix=None):
    total = sum(counts.values())
    mix = mix or _DEFAULT_MIX
    exclude_block = ""
    if exclude:
        listed = "\n".join(f"- {q}" for q in exclude[:40])
        exclude_block = (
            "\nALREADY ASKED (do not repeat these questions or test the same concept):\n"
            f"{listed}\n"
        )
    return f"""You are a senior interviewer preparing a live interview for the role: {job_title}.

CANDIDATE RESUME
{_clip(resume_text, RESUME_CHARS_MAX)}

JOB DESCRIPTION
{_clip(job_description, JD_CHARS_MAX)}
{exclude_block}
TASK
1. In "plan", first name the 3-4 BASELINE skills most prominent across the resume and JD: the core skills,
   tools or methods of this role that any interviewer in this field would check first (for an engineer
   that may be the main language and framework; for an analyst the main BI tool and SQL; for a salesperson the
   sales method and CRM; use whatever fits this role). Then list the candidate's main topics (concepts,
   features, methods or techniques their work involves, named as topics, not as projects) and the JD's
   requirements, mandatory ones first.
   Make sure each mandatory JD skill gets at least one question where the count allows; with a long JD,
   cover the mandatory skills before nice-to-haves and never spend two questions on one minor tool.
2. Write exactly {total} questions: {counts['beginner']} beginner, {counts['medium']} medium, {counts['hard']} hard.
   {mix} Give every question a distinct "topic"; never repeat one.
   Difficulty is depth: beginner is a direct fundamentals question on a named skill, medium is a direct
   how-it-works question or a scenario or walkthrough, hard is a multi-constraint design, diagnosis or
   trade-off. At least half of the beginner questions must be fundamentals on the BASELINE skills of this
   role, before spending questions on advanced or niche topics.

{_style_rules()}

Return ONLY JSON:
{{"plan": {{"baseline_skills": ["..."], "candidate_topics": ["..."], "jd_requirements": ["..."]}},
  "questions": [{{"question": "...", "difficulty": "beginner|medium|hard", "source": "work|topic|jd", "topic": "..."}}]}}"""


def _build_review_prompt(job_title, resume_text, job_description, questions, counts, mix=None):
    listed = json.dumps(questions, indent=1)
    if mix:
        anchoring = f"Keep this source mix intact: {mix}"
    else:
        anchoring = (
            "Also make sure about a third of the questions name the candidate's own project or employer; if "
            "fewer do, rewrite some questions to anchor in their real work from the resume."
        )
    return f"""You are reviewing interview questions for the role: {job_title}.

CANDIDATE RESUME
{_clip(resume_text, RESUME_CHARS_MAX)}

JOB DESCRIPTION
{_clip(job_description, JD_CHARS_MAX)}

DRAFT QUESTIONS
{listed}

Check each question and rewrite only the ones that fail. A question fails if it:
- is technically wrong or has a false premise,
- invents a past incident, number or outcome in the candidate's work, or claims they used a skill their resume lacks,
- has awkward or ungrammatical wording, a repeated word or opener, or a fragment,
- joins two unrelated topics in one question; split it so each question tests one subject,
- brings in a tool, method or example from a different field than this role's,
- is a one-keyword lookup at beginner level, or an invented scenario where a direct fundamentals question
  on the named skill was wanted, or a single-fact answer at hard level,
- is a checklist of many dimensions, or is padded without concrete detail,
- has a difficulty label that does not match its depth (rewrite it to fit its label; do not relabel it,
  for example a beginner question must not ask for a diagnosis plus a decision),
- has a hard question over 60 words or with more than 3 parts,
- is a beginner question about the candidate's own project (relabel is not allowed, so rewrite it as a direct
  fundamentals question on the skill and move the project anchor to a medium or hard question),
- refers to something vaguely ("the database integration typically used in X") instead of naming it,
- asks the candidate to choose, pick or name a project or past work ("Choose a project you used X in and
  name it"); rewrite it as a direct question on the topic, or name the project from the resume,
- has an awkward subject/verb construction such as "let a question retrieve ...",
- uses an employer or project name as a possessive or modifier ("Acme's pricing model", "the Acme
  pipeline"); rewrite as "In your work at Acme, ... the pricing model",
- is a hard question that is really a knowledge question ("how do A, B and C support D") with no concrete
  situation or constraints; rewrite it around a realistic scenario,
- tests the same concept as another question (compare every pair, even across difficulties). Two questions
  built around the same underlying idea or failure mode count as the same concept; keep one and rewrite the
  other on a different topic.
Check baseline coverage: identify the 3-4 most prominent baseline skills of this role in the resume and JD.
Each should have at least one direct fundamentals question; if one is missing, rewrite the most advanced or
redundant question into a direct question on it, keeping its difficulty label.
Check shape: at most half the questions are scenarios, and at least a third are direct questions about a named
skill; if a core skill of this role is only tested through scenarios, rewrite a question to ask about it
directly.
Check JD coverage: every mandatory JD skill should appear in at least one question where the count allows,
and no minor tool should take two questions. If a mandatory skill is missing, rewrite the weakest or most
redundant question to cover it.
{anchoring}
Keep the count and the difficulty split exactly: {counts['beginner']} beginner, {counts['medium']} medium, {counts['hard']} hard.

Return ONLY JSON: {{"questions": [{{"question": "...", "difficulty": "beginner|medium|hard", "source": "work|topic|jd", "topic": "..."}}]}}"""


def _parse_questions(raw):
    parsed = None
    try:
        parsed = _parse_llm_json_object(raw)
    except Exception:
        parsed = None
    items = None
    if isinstance(parsed, dict):
        items = parsed.get("questions")
    if not isinstance(items, list):
        try:
            items = extract_json_array(raw or "")
        except Exception:
            items = []
    out = []
    for item in items or []:
        if isinstance(item, str):
            item = {"question": item}
        if not isinstance(item, dict):
            continue
        text = str(item.get("question") or "").strip()
        level = str(item.get("difficulty") or "").strip().lower()
        if not text or level not in _LEVELS:
            continue
        out.append(
            {
                "question": text,
                "difficulty": level,
                "source": str(item.get("source") or "").strip().lower(),
                "topic": str(item.get("topic") or "").strip(),
            }
        )
    return out


def _counts_ok(questions, counts):
    return all(sum(1 for q in questions if q["difficulty"] == lvl) == counts[lvl] for lvl in _LEVELS)


def _fit_to_counts(questions, counts):
    """Trim extras per level; shortfalls are returned as-is (caller decides)."""
    out = []
    for lvl in _LEVELS:
        out.extend([q for q in questions if q["difficulty"] == lvl][: counts[lvl]])
    return out


def _call(prompt, model, temperature, label):
    response = try_ollama_chat(
        prompt.strip(),
        model=model,
        max_tokens=DIRECT_QUESTION_MAX_TOKENS,
        temperature=temperature,
    )
    raw = (response.get("message") or {}).get("content") or ""
    questions = _parse_questions(raw)
    print(f"[INFO] Direct {label}: parsed {len(questions)} question(s)")
    return questions


def generate_direct_questions(
    resume_text,
    job_title,
    job_description,
    beginner_count=2,
    medium_count=2,
    hard_count=2,
    model="llama3",
    exclude_questions=None,
    review=True,
    mix=None,
):
    """Return {"beginner": [...], "medium": [...], "hard": [...]} in the standard question shape.

    `mix` is optional source-mix guidance from mix_instruction() for blend/split/hybrid.
    """
    counts = {
        "beginner": max(0, int(beginner_count or 0)),
        "medium": max(0, int(medium_count or 0)),
        "hard": max(0, int(hard_count or 0)),
    }
    result = {lvl: [] for lvl in _LEVELS}
    if sum(counts.values()) <= 0:
        return result
    exclude = [str(q).strip() for q in (exclude_questions or []) if str(q).strip()]

    draft = []
    plan_prompt = _build_plan_prompt(job_title, resume_text, job_description, counts, exclude, mix)
    for attempt in range(DIRECT_MAX_ATTEMPTS):
        try:
            candidate = _call(plan_prompt, model, DIRECT_QUESTION_TEMPERATURE, f"plan+write try {attempt + 1}")
        except Exception as e:
            print(f"[WARN] Direct plan+write failed (try {attempt + 1}): {e}")
            continue
        if len(candidate) > len(draft):
            draft = candidate
        if _counts_ok(candidate, counts):
            draft = candidate
            break
    draft = _fit_to_counts(draft, counts)
    if not draft:
        return result

    final = draft
    if review:
        try:
            reviewed = _fit_to_counts(
                _call(
                    _build_review_prompt(job_title, resume_text, job_description, draft, counts, mix),
                    model,
                    DIRECT_REVIEW_TEMPERATURE,
                    "review",
                ),
                counts,
            )
            if _counts_ok(reviewed, counts):
                final = reviewed
            else:
                print("[WARN] Direct review returned a wrong count; keeping the draft")
        except Exception as e:
            print(f"[WARN] Direct review failed; keeping the draft: {e}")

    for q in final:
        lvl = q["difficulty"]
        result[lvl].append(
            {
                "question": q["question"],
                "difficulty": lvl,
                "weight": _WEIGHTS[lvl],
                "resume_anchor": q.get("topic", "") if q.get("source") in ("work", "topic") else "",
                "jd_anchor": q.get("topic", "") if q.get("source") == "jd" else "",
            }
        )
    print(
        "[DONE] Direct questions -> "
        + ", ".join(f"{lvl}: {len(result[lvl])}" for lvl in _LEVELS)
    )
    return result
