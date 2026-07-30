"""LLM (+ heuristic fallback) checks that uploaded text is a resume or JD."""
from __future__ import annotations

import json
import re

from common.document_validation import (
    _is_likely_job_description,
    _is_likely_resume,
    validate_extracted_document_text,
)

RESUME_TYPE_REJECT_MESSAGE = (
    "The uploaded file does not look like a resume or CV. "
    "Please upload a document with your work experience, education, skills, or projects."
)

JD_TYPE_REJECT_MESSAGE = (
    "The job description does not look like a real job posting. "
    "Please provide a role description with responsibilities, requirements, or qualifications."
)

_MAX_EXCERPT = 3500


def _excerpt(text: str, limit: int = _MAX_EXCERPT) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit] + "\n...[truncated]..."


def _parse_bool_flag(raw: str, key: str):
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and key in parsed:
            return bool(parsed[key])
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end])
            if isinstance(parsed, dict) and key in parsed:
                return bool(parsed[key])
        except json.JSONDecodeError:
            pass
    # Soft regex fallback for models that wrap JSON poorly
    match = re.search(
        rf'"{re.escape(key)}"\s*:\s*(true|false)',
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).lower() == "true"
    return None


def _llm_bool_classify(prompt: str, key: str, model: str):
    from INTERVIEW.generation_utils import try_ollama_chat

    response = try_ollama_chat(prompt.strip(), model=model, max_retries=2, max_tokens=80)
    raw = ((response or {}).get("message") or {}).get("content") or ""
    return _parse_bool_flag(raw, key), raw


def classify_is_resume(resume_text: str, model: str = "llama3"):
    """
    Returns (is_resume, error_message).
    Runs basic text validation, then an LLM check with heuristic fallback.
    """
    is_valid, msg = validate_extracted_document_text(
        resume_text,
        min_chars=100,
        min_words=15,
        min_alpha_ratio=0.35,
        doc_label="resume",
    )
    if not is_valid:
        return False, msg

    excerpt = _excerpt(resume_text)
    prompt = f"""You are a strict document gatekeeper for an interview-prep app.
Decide if the document below is a REAL candidate resume/CV that could be used to interview someone.

Document excerpt:
\"\"\"{excerpt}\"\"\"

Return ONLY valid JSON (no markdown, no explanation):
{{"is_resume": true}}
or
{{"is_resume": false}}

DEFAULT: if unsure → false.

Accept (true) ONLY if MOST of these are clearly present for ONE person:
- personal/professional identity (name and/or contact), AND
- career content such as work experience / employment history / roles held, AND/OR education, AND/OR skills, AND/OR projects
- written as that person's background (first-person or third-person about the candidate), not as a hiring post

Reject (false) for ANY of these (including when a tester uploads random files):
- job descriptions / job postings / "we are hiring" / role requirements for an open position
- invoices, receipts, bills, bank statements, tax forms, contracts, NDAs
- essays, stories, novels, poems, blog posts, news articles, Wikipedia-like text
- recipes, manuals, textbooks, lecture notes, homework, research papers (unless clearly framed as a personal CV)
- random notes, to-do lists, chat logs, emails, meeting minutes
- lorem ipsum / placeholder / gibberish / keyboard smash / repeated filler
- marketing brochures, product docs, slide decks without a personal career profile
- code dumps, config files, logs, spreadsheets of unrelated data
- company policies, handbooks, offer letters about employment terms (not a CV)
- a pasted job description pretending to be a resume
- anything that is mainly about a ROLE TO FILL rather than a PERSON'S HISTORY

Be skeptical. One or two buzzwords like "skills" or "experience" alone are NOT enough.
Only return true for a genuine resume/CV.
"""

    try:
        parsed, raw = _llm_bool_classify(prompt, "is_resume", model)
        if parsed is True:
            return True, ""
        if parsed is False:
            return False, RESUME_TYPE_REJECT_MESSAGE
        snippet = (raw or "").strip().replace("\n", " ")[:120]
        print(
            "[WARN] LLM resume-type classification unusable; using strict heuristic. "
            f"snippet={snippet!r}"
        )
    except Exception as exc:
        print(f"[WARN] LLM resume-type classification failed; using strict heuristic: {exc}")

    # Strict fallback: require stronger keyword evidence than the soft shared helper.
    if _is_likely_resume(resume_text) and _strict_resume_signals(resume_text):
        return True, ""
    return False, RESUME_TYPE_REJECT_MESSAGE


def _strict_resume_signals(text: str) -> bool:
    """Extra gate for heuristic fallback — random docs with one keyword must not pass."""
    lower = (text or "").lower()
    section_hits = sum(
        1
        for term in (
            "experience",
            "education",
            "skills",
            "projects",
            "employment",
            "work history",
            "professional summary",
            "certifications",
        )
        if term in lower
    )
    identity_hits = sum(
        1
        for term in ("email", "phone", "@", "linkedin", "github", "resume", "curriculum vitae", "cv")
        if term in lower
    )
    return section_hits >= 2 and identity_hits >= 1


def classify_is_job_description(job_title: str, job_description: str, model: str = "llama3"):
    """
    Returns (is_jd, error_message).
    Runs basic text validation, then an LLM check with heuristic fallback.
    """
    title = (job_title or "").strip()
    description = (job_description or "").strip()
    combined = f"{title}\n{description}".strip()

    is_valid, msg = validate_extracted_document_text(
        description or combined,
        min_chars=30,
        min_words=6,
        min_alpha_ratio=0.45,
        doc_label="job description",
    )
    if not is_valid:
        return False, msg

    excerpt = _excerpt(combined)
    prompt = f"""You are a strict document gatekeeper for an interview-prep app.
Decide if the text below is a REAL job description / job posting for an open role.

Job title provided by user: {title or "(missing)"}

Document excerpt:
\"\"\"{excerpt}\"\"\"

Return ONLY valid JSON (no markdown, no explanation):
{{"is_job_description": true}}
or
{{"is_job_description": false}}

DEFAULT: if unsure → false.

Accept (true) ONLY if the text clearly describes a ROLE TO HIRE FOR, with MOST of:
- what the person in the role will do (responsibilities / duties / day-to-day), AND/OR
- what is required (qualifications / requirements / must-have skills / experience level), AND
- hiring framing (about the role, about the team/company, who should apply, preferred qualifications)

Reject (false) for ANY of these (including when a tester uploads random content):
- resumes / CVs / personal career histories / "my experience at Company X"
- invoices, receipts, bills, bank statements, tax forms, contracts, NDAs
- essays, stories, novels, poems, blog posts, news articles
- recipes, manuals, textbooks, lecture notes, homework, research papers
- random notes, to-do lists, chat logs, emails, meeting minutes
- lorem ipsum / placeholder / gibberish / keyboard smash / repeated filler
- marketing fluff with no real role duties or requirements
- code dumps, config files, logs, unrelated data tables
- company policies / handbooks that are not a job posting
- a resume pasted into the job-description field
- a job title alone with no real role content
- text that is mainly about ONE PERSON'S past jobs rather than an open position

Be skeptical. Words like "developer" or "engineer" alone are NOT enough.
Only return true for a genuine job posting / role description.
"""

    try:
        parsed, raw = _llm_bool_classify(prompt, "is_job_description", model)
        if parsed is True:
            return True, ""
        if parsed is False:
            return False, JD_TYPE_REJECT_MESSAGE
        snippet = (raw or "").strip().replace("\n", " ")[:120]
        print(
            "[WARN] LLM JD-type classification unusable; using strict heuristic. "
            f"snippet={snippet!r}"
        )
    except Exception as exc:
        print(f"[WARN] LLM JD-type classification failed; using strict heuristic: {exc}")

    if _is_likely_job_description(combined) and _strict_jd_signals(combined):
        return True, ""
    return False, JD_TYPE_REJECT_MESSAGE


def _strict_jd_signals(text: str) -> bool:
    """Extra gate for heuristic fallback — random docs with one keyword must not pass."""
    lower = (text or "").lower()
    primary_hits = sum(
        1
        for term in (
            "responsibilities",
            "requirements",
            "qualifications",
            "job description",
            "about the role",
            "what you'll do",
            "what you will do",
            "we are looking for",
            "key responsibilities",
        )
        if term in lower
    )
    secondary_hits = sum(
        1
        for term in (
            "apply",
            "full-time",
            "part-time",
            "remote",
            "hybrid",
            "salary",
            "benefits",
            "years of experience",
            "preferred qualifications",
            "must have",
        )
        if term in lower
    )
    return primary_hits >= 1 and (primary_hits + secondary_hits) >= 2
