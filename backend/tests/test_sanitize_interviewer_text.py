from INTERVIEW.Interview_functions import sanitize_interviewer_display_text


def test_strips_bold_markdown():
    raw = (
        "1. **High-Dimensional Data**: Vector databases handle many dimensions.\n"
        "2. **Efficient Similarity Search**: They are optimized for fast searches."
    )
    clean = sanitize_interviewer_display_text(raw)
    assert "**" not in clean
    assert "High-Dimensional Data" in clean
    assert "Efficient Similarity Search" in clean
    assert "asterisk" not in clean.lower()


def test_strips_italic_and_code():
    raw = "Use *embeddings* and `faiss` for search."
    clean = sanitize_interviewer_display_text(raw)
    assert "*" not in clean
    assert "`" not in clean
    assert "embeddings" in clean
    assert "faiss" in clean


def test_streaming_holds_trailing_opener():
    partial = sanitize_interviewer_display_text("Hello **", streaming=True)
    assert not partial.endswith("*")
    complete = sanitize_interviewer_display_text("Hello **world**", streaming=True)
    assert complete == "Hello world"
