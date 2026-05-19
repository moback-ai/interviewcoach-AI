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


def validate_resume_text(text):
    return validate_extracted_document_text(
        text,
        min_chars=100,
        min_words=15,
        min_alpha_ratio=0.35,
        doc_label="resume",
    )


def validate_job_description_extracted_text(text):
    return validate_extracted_document_text(
        text,
        min_chars=30,
        min_words=6,
        min_alpha_ratio=0.45,
        doc_label="job description",
    )
