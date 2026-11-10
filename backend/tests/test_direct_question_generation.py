import json
from unittest.mock import patch

import pytest

from INTERVIEW import direct_question_generation as dqg


def _reply(questions):
    return {"message": {"content": json.dumps({"plan": {}, "questions": questions})}}


def _q(level, text, source="work"):
    return {"question": text, "difficulty": level, "source": source, "topic": "t"}


DRAFT = [
    _q("beginner", "How does an extract differ from a live connection?", "topic"),
    _q("medium", "Why would a LOD expression return a different total than a table calculation?"),
    _q("hard", "Dashboard load takes 30 seconds on 5M rows; what do you check first?", "jd"),
]
COUNTS = dict(beginner_count=1, medium_count=1, hard_count=1)


def _run(replies, **kw):
    with patch.object(dqg, "try_ollama_chat", side_effect=replies) as chat:
        out = dqg.generate_direct_questions("resume", "BI Dev", "jd", model="m", **COUNTS, **kw)
    return out, chat


def test_two_calls_and_standard_shape():
    fixed = [dict(q, question=q["question"] + " Be specific.") for q in DRAFT]
    out, chat = _run([_reply(DRAFT), _reply(fixed)])
    assert chat.call_count == 2
    assert [len(out[k]) for k in ("beginner", "medium", "hard")] == [1, 1, 1]
    assert out["hard"][0]["weight"] == 5
    assert out["beginner"][0]["question"].endswith("Be specific.")
    assert out["hard"][0]["jd_anchor"] == "t" and out["hard"][0]["resume_anchor"] == ""


def test_review_with_wrong_count_keeps_draft():
    out, _ = _run([_reply(DRAFT), _reply(DRAFT[:2])])
    assert [len(out[k]) for k in ("beginner", "medium", "hard")] == [1, 1, 1]
    assert out["beginner"][0]["question"] == DRAFT[0]["question"]


def test_review_failure_keeps_draft():
    out, _ = _run([_reply(DRAFT), RuntimeError("boom")])
    assert out["medium"][0]["question"] == DRAFT[1]["question"]


def test_retries_when_draft_count_is_wrong_and_trims_extras():
    extra = DRAFT + [_q("hard", "Another hard one?")]
    out, chat = _run([_reply(DRAFT[:1]), _reply(extra), _reply(DRAFT)])
    assert [len(out[k]) for k in ("beginner", "medium", "hard")] == [1, 1, 1]
    assert chat.call_count == 3  # 2 draft attempts + 1 review


def test_empty_when_every_attempt_fails():
    with pytest.raises(RuntimeError, match="The AI provider rejected the request"):
        _run([RuntimeError("x")] * dqg.DIRECT_MAX_ATTEMPTS)


def test_prompts_have_no_tool_or_employer_specific_examples():
    # The writer/reviewer prompts must work for any field; keep stack- and employer-specific
    # examples (which bias the model toward that stack) out of them.
    counts = dict(beginner=1, medium=1, hard=1)
    text = (
        dqg._build_plan_prompt("Role", "resume", "jd", counts, [])
        + dqg._build_review_prompt("Role", "resume", "jd", DRAFT, counts)
    ).lower()
    for term in ("terraform", "kubernetes", "kafka", "docker", "git rebase", "cartly", "paystream",
                 "gamification", "keyset", "idempoten", "django", "postgres"):
        assert term not in text, term


def test_mix_instruction_per_mode_reaches_both_prompts():
    for mode, marker in (("blend", "Blend the resume"), ("split", "Split by source"), ("hybrid", "three buckets")):
        mix = dqg.mix_instruction(mode, 10, resume_pct=60, jd_pct=40, blend_pct_resume=70, blend_pct_jd=30)
        assert marker in mix
        _, chat = _run([_reply(DRAFT), _reply(DRAFT)], mix=mix)
        assert mix in chat.call_args_list[0].args[0]
        assert mix in chat.call_args_list[1].args[0]


def test_split_mix_counts_add_up():
    mix = dqg.mix_instruction("split", 10, resume_pct=60, jd_pct=40)
    assert "Exactly 6 questions" in mix and "exactly 4 come ONLY from JD" in mix


def test_core_mix_keeps_default_thirds():
    assert dqg.mix_instruction("core", 6) == dqg._DEFAULT_MIX
    assert "in thirds" in dqg._build_plan_prompt("Role", "r", "j", dict(beginner=1, medium=1, hard=1), [])


def test_exclude_questions_are_in_the_prompt():
    _, chat = _run([_reply(DRAFT), _reply(DRAFT)], exclude_questions=["What is an extract?"])
    assert "What is an extract?" in chat.call_args_list[0].args[0]
