from common.document_type_classification import (
    JD_TYPE_REJECT_MESSAGE,
    RESUME_TYPE_REJECT_MESSAGE,
    _parse_bool_flag,
    classify_is_job_description,
    classify_is_resume,
)


def test_parse_bool_flag_json():
    assert _parse_bool_flag('{"is_resume": true}', "is_resume") is True
    assert _parse_bool_flag('{"is_resume": false}', "is_resume") is False


def test_parse_bool_flag_wrapped():
    raw = 'Sure.\n{"is_job_description": true}\n'
    assert _parse_bool_flag(raw, "is_job_description") is True


def test_classify_resume_rejects_empty(monkeypatch):
    ok, msg = classify_is_resume("   ")
    assert ok is False
    assert "empty" in msg.lower() or "readable" in msg.lower()


def test_classify_resume_llm_false(monkeypatch):
    def fake_llm(prompt, model="llama3", max_retries=2, max_tokens=80):
        return {"message": {"content": '{"is_resume": false}'}}

    monkeypatch.setattr(
        "INTERVIEW.generation_utils.try_ollama_chat",
        fake_llm,
    )
    text = (
        "This is a long invoice for office supplies. "
        "Please pay the amount due by the end of the month. "
        "Itemized charges include paper, toner, and desks. "
        "Contact billing for questions about this statement."
    )
    ok, msg = classify_is_resume(text)
    assert ok is False
    assert msg == RESUME_TYPE_REJECT_MESSAGE


def test_classify_resume_llm_true(monkeypatch):
    def fake_llm(prompt, model="llama3", max_retries=2, max_tokens=80):
        return {"message": {"content": '{"is_resume": true}'}}

    monkeypatch.setattr(
        "INTERVIEW.generation_utils.try_ollama_chat",
        fake_llm,
    )
    text = (
        "Jane Doe — Software Engineer. Experience: built APIs at Acme. "
        "Education: B.S. Computer Science. Skills: Python, SQL, AWS. "
        "Projects: interview coach platform and payment services."
    )
    ok, msg = classify_is_resume(text)
    assert ok is True
    assert msg == ""


def test_classify_jd_llm_false(monkeypatch):
    def fake_llm(prompt, model="llama3", max_retries=2, max_tokens=80):
        return {"message": {"content": '{"is_job_description": false}'}}

    monkeypatch.setattr(
        "INTERVIEW.generation_utils.try_ollama_chat",
        fake_llm,
    )
    ok, msg = classify_is_job_description(
        "My life story",
        "I was born in a small town and enjoy hiking on weekends with my dog. "
        "This document is a personal essay about travel and hobbies.",
    )
    assert ok is False
    assert msg == JD_TYPE_REJECT_MESSAGE
