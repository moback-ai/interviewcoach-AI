"""Unit tests for interview audio merge ordering helpers."""

from app import (
    _audio_clip_sort_key,
    _audio_turn_timestamp,
    _count_candidate_responses_from_transcript,
)


def test_audio_timestamp_supports_seconds_and_micros():
    assert _audio_turn_timestamp("user_20260731T120000.wav") == "20260731T120000"
    assert _audio_turn_timestamp("interviewer_abcd1234_20260731T120000123456.wav") == (
        "20260731T120000123456"
    )


def test_same_second_keeps_user_before_interviewer():
    names = [
        "interviewer_deadbeef_20260731T120000.wav",
        "user_20260731T120000.wav",
        "interviewer_cafebabe_20260731T120001.wav",
        "user_20260731T120001.wav",
    ]
    ordered = sorted(names, key=_audio_clip_sort_key)
    assert ordered == [
        "user_20260731T120000.wav",
        "interviewer_deadbeef_20260731T120000.wav",
        "user_20260731T120001.wav",
        "interviewer_cafebabe_20260731T120001.wav",
    ]


def test_count_candidate_responses():
    transcript = [
        {"role": "assistant", "content": "Hi"},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Tell me more"},
        {"role": "candidate", "content": "Sure"},
        {"role": "user", "content": "Done"},
    ]
    assert _count_candidate_responses_from_transcript(transcript) == 3
