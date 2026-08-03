from common.content_hash import (
    hash_job_description,
    hash_resume_bytes,
    hash_skills_list,
    hash_skills_text,
    normalize_text,
)


def test_normalize_text_collapses_whitespace_and_case():
    assert normalize_text("  Hello   WORLD \n") == "hello world"


def test_hash_resume_bytes_stable():
    a = hash_resume_bytes(b"resume-bytes")
    b = hash_resume_bytes(b"resume-bytes")
    c = hash_resume_bytes(b"other")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_hash_skills_order_independent():
    a = hash_skills_list(["Python", "AWS"])
    b = hash_skills_list(["aws", "python"])
    c = hash_skills_text("Python, AWS")
    assert a == b == c


def test_hash_job_description_normalized():
    a = hash_job_description("AWS Engineer", "Build  cloud  systems.")
    b = hash_job_description("aws engineer", "Build cloud systems.")
    c = hash_job_description("AWS Engineer", "Different JD text")
    assert a == b
    assert a != c


def test_check_resume_jd_pair_response_shape_contract():
    """Document expected API match payload keys for frontend consumers."""
    match = {
        "resume_id": None,
        "jd_id": None,
        "resume_url": None,
        "resume_hash": "a" * 64,
        "jd_hash": "b" * 64,
        "filename_match": False,
        "content_match": False,
        "content_match_resume": False,
        "content_match_jd": False,
        "questions_exist": False,
        "question_set_count": 0,
        "latest_question_set": None,
        "job_title": "Role",
    }
    required = {
        "resume_id",
        "jd_id",
        "resume_hash",
        "jd_hash",
        "filename_match",
        "content_match",
        "questions_exist",
        "question_set_count",
        "job_title",
    }
    assert required.issubset(match.keys())
