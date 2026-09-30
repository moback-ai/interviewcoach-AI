from INTERVIEW.Interview_functions import (
    _intro_off_script_redirect,
    _is_greeting_or_farewell,
    _is_intro_off_script,
    _is_substantive_response,
    _looks_like_candidate_question,
    _looks_like_self_intro,
    assess_icebreaker_response,
    assess_intro_progress,
    generate_contextual_intro_reply,
)


def test_farewell_detected():
    assert _is_greeting_or_farewell("bye bye bye")
    assert _is_greeting_or_farewell("goodbye")
    assert _is_greeting_or_farewell("hi")
    assert not _is_greeting_or_farewell(
        "My name is Priya and I graduated in CS from NIT in 2024"
    )


def test_candidate_question_detected():
    assert _looks_like_candidate_question("what is a vector database?")
    assert _looks_like_candidate_question("Hi hi hi what is a vector database?")
    assert not _looks_like_candidate_question(
        "My name is Neeraj. I did BTech in ECE at MIT Manipal."
    )


def test_tech_question_not_substantive_or_intro():
    text = "Hi hi hi what is a vector database?"
    assert _is_intro_off_script(text)
    assert not _is_substantive_response(text)
    assert not _looks_like_self_intro(text)


def test_intro_reply_redirects_bye_without_llm():
    result = generate_contextual_intro_reply(
        "React Developer",
        "Build React apps",
        [{"role": "assistant", "content": "Please introduce yourself."}],
        "bye bye bye",
    )
    message = result["message"].lower()
    assert "introduce yourself" in message
    assert "great day" not in message
    assert "thank you for your time" not in message


def test_intro_reply_redirects_tech_question_without_llm():
    result = generate_contextual_intro_reply(
        "React Developer",
        "Build React apps",
        [{"role": "assistant", "content": "Please introduce yourself."}],
        "what is a vector database?",
    )
    message = result["message"].lower()
    assert "later" in message
    assert "introduce yourself" in message
    assert "high-dimensional" not in message


def test_assess_intro_progress_bye_is_wait():
    history = [
        {"role": "assistant", "content": "Please introduce yourself."},
        {"role": "user", "content": "bye bye bye"},
        {"role": "assistant", "content": _intro_off_script_redirect("bye bye bye")},
    ]
    assert assess_intro_progress(history) == "wait"


def test_assess_intro_progress_tech_is_retry():
    history = [
        {"role": "assistant", "content": "Please introduce yourself."},
        {"role": "user", "content": "what is a vector database?"},
    ]
    assert assess_intro_progress(history) == "retry"


def test_icebreaker_rejects_tech_question():
    assert (
        assess_icebreaker_response(
            "what is a vector database?",
            "What's your favorite food?",
        )
        == "retry"
    )
