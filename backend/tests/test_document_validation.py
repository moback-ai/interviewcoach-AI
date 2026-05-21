from common.document_validation import (
    EMPTY_DOCUMENT_MESSAGE,
    SCANNED_PDF_MESSAGE,
    validate_extracted_document_text,
    validate_job_description_extracted_text,
    validate_resume_text,
)


def test_validate_resume_accepts_readable_text():
    text = " ".join(["Experienced software engineer"] * 20)
    ok, err = validate_resume_text(text)
    assert ok is True
    assert err == ""


def test_validate_resume_rejects_empty():
    ok, err = validate_resume_text("   ")
    assert ok is False
    assert err == EMPTY_DOCUMENT_MESSAGE


def test_validate_resume_rejects_garbage_blob():
    ok, err = validate_resume_text("x" * 200)
    assert ok is False
    assert "readable" in err.lower() or err == SCANNED_PDF_MESSAGE


def test_validate_jd_allows_shorter_text():
    ok, err = validate_job_description_extracted_text(
        "Senior backend engineer. Python, PostgreSQL, AWS."
    )
    assert ok is True
    assert err == ""


def test_validate_extracted_document_rejects_too_few_words():
    ok, err = validate_extracted_document_text(
        "alpha beta gamma delta epsilon zeta eta theta iota kappa",
        min_chars=40,
        min_words=12,
    )
    assert ok is False
    assert "readable words" in err.lower()
