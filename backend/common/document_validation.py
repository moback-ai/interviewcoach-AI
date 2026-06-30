"""Shared validation for extracted resume/JD text (empty, garbage, scanned PDFs)."""
import re

EMPTY_DOCUMENT_MESSAGE = (
    "The uploaded file appears to be empty or missing enough readable text. "
    "Please upload a valid document with selectable text."
)

SCANNED_PDF_MESSAGE = (
    "This PDF looks like a scanned image or has very little selectable text. "
    "Please upload a text-based PDF, DOCX, or TXT file."
)


def _word_count(text):
    return len(re.findall(r"[A-Za-z0-9]+", text or ""))


def _alpha_ratio(text):
    symbol_count = sum(1 for ch in text if not ch.isspace())
    if not symbol_count:
        return 0.0
    alpha_count = sum(1 for ch in text if ch.isalpha())
    return alpha_count / symbol_count


def validate_extracted_document_text(
    text,
    *,
    min_chars=80,
    min_words=12,
    min_alpha_ratio=0.35,
    doc_label="document",
):
    """
    Returns (is_valid, error_message).
    """
    cleaned = (text or "").strip()
    if not cleaned:
        return False, EMPTY_DOCUMENT_MESSAGE

    if len(cleaned) < min_chars:
        return False, (
            f"The {doc_label} is too short to parse reliably. "
            "Please upload a complete file with readable content."
        )

    words = _word_count(cleaned)
    if words < min_words:
        return False, (
            f"The {doc_label} does not contain enough readable words. "
            "It may be blank or scanned without OCR text."
        )

    if _alpha_ratio(cleaned) < min_alpha_ratio:
        return False, SCANNED_PDF_MESSAGE

  # Heuristic: very long runs without spaces often indicate binary/garbage extraction
    if re.search(r"\S{120,}", cleaned):
        return False, SCANNED_PDF_MESSAGE

    return True, ""


def _is_likely_resume(text):
    text_lower = (text or "").lower()
    primary_terms = ["experience", "education", "skills", "projects", "employment", "professional history", "cv", "resume", "certifications"]
    secondary_terms = [
        "contact", "email", "phone", "gpa", "university", "college", "school", "summary", 
        "objective", "achievements", "profile", "developer", "engineer", "software", "analyst", 
        "manager", "designer", "consultant", "technical", "senior", "junior", "lead"
    ]
    
    score = 0
    for term in primary_terms:
        if term in text_lower:
            score += 2
    for term in secondary_terms:
        if term in text_lower:
            score += 1
    return score >= 3


def _is_likely_job_description(text):
    text_lower = (text or "").lower()
    primary_terms = ["responsibilities", "requirements", "qualifications", "job description", "about the role", "key responsibilities", "skills required"]
    secondary_terms = [
        "experience", "duties", "benefits", "compensation", "salary", "apply", "role", 
        "position", "full-time", "part-time", "candidate", "seeking", "looking for", "developer", 
        "engineer", "software", "analyst", "manager", "designer", "consultant", "team",
        "senior", "junior", "lead", "backend", "frontend", "fullstack"
    ]
    
    score = 0
    for term in primary_terms:
        if term in text_lower:
            score += 2
    for term in secondary_terms:
        if term in text_lower:
            score += 1
    return score >= 2


def validate_resume_text(text):
    is_valid, msg = validate_extracted_document_text(
        text,
        min_chars=100,
        min_words=15,
        min_alpha_ratio=0.35,
        doc_label="resume",
    )
    if not is_valid:
        return False, msg

    if not _is_likely_resume(text):
        return False, (
            "The uploaded file does not appear to be a valid resume. "
            "Please upload a document containing work experience, education, skills, or projects."
        )
    return True, ""


def validate_job_description_extracted_text(text):
    is_valid, msg = validate_extracted_document_text(
        text,
        min_chars=30,
        min_words=6,
        min_alpha_ratio=0.45,
        doc_label="job description",
    )
    if not is_valid:
        return False, msg

    if not _is_likely_job_description(text):
        return False, (
            "The uploaded file does not appear to be a valid job description. "
            "Please upload a document containing role responsibilities, requirements, or qualifications."
        )
    return True, ""
