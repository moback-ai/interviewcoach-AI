"""Free-tier quota and shared STARTED interview creation."""

from __future__ import annotations

import json
import logging
import uuid

from common.db import query_one, run_transaction
from common.payment_fulfillment import (
    _compute_attempt_number,
    _fallback_link_questions,
    _link_questions,
    _verify_ownership,
    snapshot_question_ids,
)
from common.runtime_config import optional_env

logger = logging.getLogger(__name__)

STARTED_INTERVIEW_STATUSES = ("STARTED", "ENDED", "completed", "ACTIVE")


class InterviewStartError(Exception):
    pass


class PaymentRequiredError(InterviewStartError):
    pass


def free_interview_limit() -> int:
    try:
        return max(0, int(optional_env("FREE_INTERVIEW_LIMIT", "2") or 2))
    except (TypeError, ValueError):
        return 2


def count_started_interviews(user_id: str) -> int:
    row = query_one(
        """
        SELECT COUNT(*) AS cnt
        FROM interviews
        WHERE user_id = %s
          AND status = ANY(%s)
        """,
        (user_id, list(STARTED_INTERVIEW_STATUSES)),
    )
    return int((row or {}).get("cnt") or 0)


def interview_quota(user_id: str) -> dict:
    limit = free_interview_limit()
    started_count = count_started_interviews(user_id)
    free_remaining = max(0, limit - started_count)
    return {
        "started_count": started_count,
        "free_limit": limit,
        "free_remaining": free_remaining,
        "payment_required": started_count >= limit,
    }


def create_started_interview_cur(
    cur,
    user_id: str,
    resume_id: str,
    jd_id: str,
    question_set: int,
    *,
    retake_from: str | None = None,
    question_ids: list[str] | None = None,
    interview_id: str | None = None,
) -> str:
    if not _verify_ownership(cur, user_id, resume_id, jd_id):
        raise InterviewStartError("Resume or job description not found")

    attempt_number = 1
    if retake_from:
        attempt_number = _compute_attempt_number(cur, user_id, resume_id, jd_id, question_set)

    new_interview_id = interview_id or str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO interviews (
            id, user_id, resume_id, jd_id, status, question_set,
            retake_from, attempt_number, scheduled_at
        )
        VALUES (%s, %s, %s, %s, 'STARTED', %s, %s, %s, now())
        RETURNING id
        """,
        (
            new_interview_id,
            user_id,
            resume_id,
            jd_id,
            question_set,
            retake_from,
            attempt_number,
        ),
    )

    resolved_question_ids = list(question_ids or [])
    if not resolved_question_ids:
        resolved_question_ids = snapshot_question_ids(cur, user_id, resume_id, jd_id, question_set)
    else:
        resolved_question_ids = [str(qid) for qid in resolved_question_ids]

    linked = _link_questions(cur, new_interview_id, resolved_question_ids)
    if linked == 0 and resolved_question_ids:
        linked = _fallback_link_questions(
            cur, new_interview_id, user_id, resume_id, jd_id, question_set
        )
    if linked == 0:
        logger.warning("No questions linked for interview %s", new_interview_id)

    return new_interview_id


def create_started_interview(
    user_id: str,
    resume_id: str,
    jd_id: str,
    question_set: int,
    *,
    retake_from: str | None = None,
    question_ids: list[str] | None = None,
) -> str:
    def _work(cur):
        return create_started_interview_cur(
            cur,
            user_id,
            resume_id,
            jd_id,
            question_set,
            retake_from=retake_from,
            question_ids=question_ids,
        )

    return run_transaction(_work)
