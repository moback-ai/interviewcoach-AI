"""Idempotent checkout fulfillment (webhook-only writer for paid interviews)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from common.db import run_transaction

logger = logging.getLogger(__name__)

SUCCESS_STATUSES = frozenset({"succeeded", "success", "completed"})
FAILURE_STATUSES = frozenset({"failed", "cancelled", "canceled"})
TERMINAL_SUCCESS_STATUSES = frozenset({"fulfilled", "paid_needs_review"})

STALE_PROCESSING_SECONDS = 300


class FulfillmentError(Exception):
    pass


class PaidNeedsReview(FulfillmentError):
    """Payment confirmed but integrity checks failed — manual review required."""


def _utcnow():
    return datetime.now(timezone.utc)


def _failure_reason_from_status(status: str) -> str:
    normalized = (status or "").lower()
    if normalized in {"cancelled", "canceled"}:
        return "provider_cancelled"
    return "provider_failed"


def _is_success_payment_status(payment_status: str) -> bool:
    return (payment_status or "").lower() in SUCCESS_STATUSES


def snapshot_question_ids(cur, user_id: str, resume_id: str, jd_id: str, question_set: int) -> list[str]:
    cur.execute(
        """
        SELECT q.id
        FROM questions q
        JOIN resumes r ON r.id = q.resume_id AND r.user_id = %s
        JOIN job_descriptions jd ON jd.id = q.jd_id AND jd.user_id = %s
        WHERE q.resume_id = %s
          AND q.jd_id = %s
          AND q.question_set = %s
          AND q.interview_id IS NULL
        ORDER BY q.created_at ASC
        """,
        (user_id, user_id, resume_id, jd_id, question_set),
    )
    rows = cur.fetchall()
    return [str(row["id"]) for row in rows]


def _metadata_matches_intent(metadata: dict[str, Any], intent: dict) -> bool:
    meta_intent_id = str(metadata.get("checkout_intent_id") or "")
    meta_user_id = str(metadata.get("user_id") or "")
    if meta_intent_id and meta_intent_id != str(intent["id"]):
        return False
    if meta_user_id and meta_user_id != str(intent["user_id"]):
        return False
    return True


def _verify_ownership(cur, user_id: str, resume_id: str, jd_id: str) -> bool:
    cur.execute(
        """
        SELECT 1
        FROM resumes r
        JOIN job_descriptions jd ON jd.id = %s AND jd.user_id = %s
        WHERE r.id = %s AND r.user_id = %s
        LIMIT 1
        """,
        (jd_id, user_id, resume_id, user_id),
    )
    return cur.fetchone() is not None


def _compute_attempt_number(cur, user_id: str, resume_id: str, jd_id: str, question_set: int) -> int:
    cur.execute(
        """
        SELECT COALESCE(MAX(attempt_number), 0) AS max_attempt
        FROM interviews
        WHERE user_id = %s AND resume_id = %s AND jd_id = %s AND question_set = %s
        """,
        (user_id, resume_id, jd_id, question_set),
    )
    row = cur.fetchone()
    return int(row["max_attempt"] or 0) + 1


def _link_questions(cur, interview_id: str, question_ids: list[str]) -> int:
    if not question_ids:
        return 0
    cur.execute(
        """
        UPDATE questions
        SET interview_id = %s
        WHERE id = ANY(%s::uuid[])
          AND interview_id IS NULL
        """,
        (interview_id, question_ids),
    )
    return cur.rowcount


def _fallback_link_questions(
    cur, interview_id: str, user_id: str, resume_id: str, jd_id: str, question_set: int
) -> int:
    cur.execute(
        """
        UPDATE questions q
        SET interview_id = %s
        FROM resumes r, job_descriptions jd
        WHERE q.resume_id = r.id AND r.user_id = %s
          AND q.jd_id = jd.id AND jd.user_id = %s
          AND q.resume_id = %s
          AND q.jd_id = %s
          AND q.question_set = %s
          AND q.interview_id IS NULL
        """,
        (interview_id, user_id, user_id, resume_id, jd_id, question_set),
    )
    return cur.rowcount


def _upsert_payment(
    cur,
    *,
    user_id: str,
    checkout_intent_id: str,
    transaction_id: str,
    amount_paise: int | None,
    payment_status: str,
    metadata: dict,
) -> None:
    is_success = _is_success_payment_status(payment_status)
    cur.execute(
        """
        INSERT INTO payments (
            user_id, checkout_intent_id, interview_id, amount, provider,
            payment_status, transaction_id, metadata, paid_at, recorded_at
        )
        VALUES (%s, %s, NULL, %s, 'dodo', %s, %s, %s::jsonb,
                CASE WHEN %s THEN now() ELSE NULL END, now())
        ON CONFLICT (transaction_id) DO UPDATE SET
            payment_status = EXCLUDED.payment_status,
            amount = COALESCE(EXCLUDED.amount, payments.amount),
            metadata = COALESCE(EXCLUDED.metadata, payments.metadata),
            checkout_intent_id = COALESCE(payments.checkout_intent_id, EXCLUDED.checkout_intent_id),
            paid_at = CASE
                WHEN EXCLUDED.payment_status IN ('succeeded', 'success', 'completed') THEN COALESCE(payments.paid_at, now())
                ELSE NULL
            END,
            recorded_at = now()
        """,
        (
            user_id,
            checkout_intent_id,
            amount_paise or 0,
            payment_status,
            transaction_id,
            json.dumps(metadata),
            is_success,
        ),
    )


def _mark_paid_needs_review(cur, intent_id: str, reason: str) -> None:
    cur.execute(
        """
        UPDATE checkout_intents
        SET status = 'paid_needs_review'
        WHERE id = %s
        """,
        (intent_id,),
    )
    logger.error("Checkout intent %s marked paid_needs_review: %s", intent_id, reason)


def _expire_intent_if_stale_cur(cur, intent_id: str) -> bool:
    cur.execute(
        """
        UPDATE checkout_intents
        SET status = 'expired', failure_reason = 'abandoned'
        WHERE id = %s
          AND status = 'pending'
          AND expires_at < now()
        RETURNING id
        """,
        (intent_id,),
    )
    return cur.fetchone() is not None


def expire_checkout_intent_if_stale(intent_id: str) -> bool:
    def _work(cur):
        return _expire_intent_if_stale_cur(cur, intent_id)

    return run_transaction(_work)


def expire_stale_checkout_intents(limit: int = 500) -> int:
    def _work(cur):
        cur.execute(
            """
            UPDATE checkout_intents
            SET status = 'expired', failure_reason = 'abandoned'
            WHERE id IN (
                SELECT id FROM checkout_intents
                WHERE status = 'pending' AND expires_at < now()
                ORDER BY expires_at ASC
                LIMIT %s
            )
            RETURNING id
            """,
            (limit,),
        )
        return len(cur.fetchall())

    return run_transaction(_work)


def mark_checkout_creation_failed(
    intent_id: str,
    *,
    http_status: int | None = None,
    error_kind: str = "dodo_checkout_api",
) -> None:
    error_metadata: dict[str, Any] = {"error_kind": error_kind}
    if http_status is not None:
        error_metadata["http_status"] = http_status

    def _work(cur):
        cur.execute(
            """
            UPDATE checkout_intents
            SET status = 'checkout_creation_failed',
                failure_reason = 'checkout_api_error',
                error_metadata = %s::jsonb
            WHERE id = %s AND status = 'pending'
            """,
            (json.dumps(error_metadata), intent_id),
        )

    run_transaction(_work)


def _record_checkout_payment_failure_cur(
    cur,
    intent_id: str,
    payment_payload: dict[str, Any],
) -> bool:
    """Record provider payment failure. Returns True if state changed, False if no-op."""
    status = (payment_payload.get("status") or "").lower()
    if status not in FAILURE_STATUSES:
        return False

    transaction_id = (payment_payload.get("payment_id") or "").strip()
    metadata = payment_payload.get("metadata") or {}
    amount_paise = payment_payload.get("amount_paise")
    failure_reason = _failure_reason_from_status(status)

    cur.execute(
        "SELECT * FROM checkout_intents WHERE id = %s FOR UPDATE",
        (intent_id,),
    )
    intent = cur.fetchone()
    if not intent:
        raise FulfillmentError(f"Checkout intent not found: {intent_id}")

    if intent["status"] in TERMINAL_SUCCESS_STATUSES:
        logger.warning(
            "Ignoring failure webhook for intent %s in terminal success status %s",
            intent_id,
            intent["status"],
        )
        return False

    if intent["status"] == "failed":
        if transaction_id:
            cur.execute(
                "SELECT transaction_id FROM payments WHERE checkout_intent_id = %s LIMIT 1",
                (intent_id,),
            )
            existing = cur.fetchone()
            if existing and str(existing["transaction_id"]) == transaction_id:
                return False
        elif intent.get("failure_reason") == failure_reason:
            return False

    if intent["status"] not in {"pending", "expired", "failed"}:
        logger.info(
            "Skipping failure webhook for intent %s in status %s",
            intent_id,
            intent["status"],
        )
        return False

    cur.execute(
        """
        UPDATE checkout_intents
        SET status = 'failed', failure_reason = %s
        WHERE id = %s
        """,
        (failure_reason, intent_id),
    )

    if transaction_id:
        _upsert_payment(
            cur,
            user_id=str(intent["user_id"]),
            checkout_intent_id=str(intent_id),
            transaction_id=transaction_id,
            amount_paise=amount_paise,
            payment_status=status,
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    return True


def record_checkout_payment_failure(intent_id: str, payment_payload: dict[str, Any]) -> bool:
    def _work(cur):
        return _record_checkout_payment_failure_cur(cur, intent_id, payment_payload)

    return run_transaction(_work)


def fulfill_checkout_intent(intent_id: str, payment_payload: dict[str, Any]) -> str | None:
    """
    Fulfill a checkout intent after successful payment.
    Returns interview_id on success, None for failure-only events.
    Raises PaidNeedsReview when payment is confirmed but fulfillment cannot proceed safely.
  """
    status = (payment_payload.get("status") or "").lower()
    metadata = payment_payload.get("metadata") or {}
    transaction_id = payment_payload.get("payment_id") or ""
    amount_paise = payment_payload.get("amount_paise")

    def _work(cur):
        cur.execute(
            "SELECT * FROM checkout_intents WHERE id = %s FOR UPDATE",
            (intent_id,),
        )
        intent = cur.fetchone()
        if not intent:
            raise FulfillmentError(f"Checkout intent not found: {intent_id}")

        if intent["status"] == "fulfilled" and intent.get("interview_id"):
            return str(intent["interview_id"])

        if status in FAILURE_STATUSES:
            _record_checkout_payment_failure_cur(cur, intent_id, payment_payload)
            return None

        if status not in SUCCESS_STATUSES:
            logger.info("Ignoring non-terminal payment status %s for intent %s", status, intent_id)
            return None

        if intent["expires_at"] and intent["expires_at"] < _utcnow():
            logger.warning(
                "Fulfilling expired checkout intent %s because provider confirmed payment",
                intent_id,
            )

        if not _metadata_matches_intent(metadata, intent):
            _upsert_payment(
                cur,
                user_id=str(intent["user_id"]),
                checkout_intent_id=str(intent_id),
                transaction_id=transaction_id,
                amount_paise=amount_paise,
                payment_status=status,
                metadata=metadata,
            )
            _mark_paid_needs_review(intent_id, "metadata mismatch")
            raise PaidNeedsReview("metadata mismatch")

        user_id = str(intent["user_id"])
        resume_id = str(intent["resume_id"])
        jd_id = str(intent["jd_id"])
        question_set = int(intent["question_set"])

        if not _verify_ownership(cur, user_id, resume_id, jd_id):
            _upsert_payment(
                cur,
                user_id=user_id,
                checkout_intent_id=str(intent_id),
                transaction_id=transaction_id,
                amount_paise=amount_paise,
                payment_status=status,
                metadata=metadata,
            )
            _mark_paid_needs_review(intent_id, "resume/jd ownership failed")
            raise PaidNeedsReview("ownership verification failed")

        _upsert_payment(
            cur,
            user_id=user_id,
            checkout_intent_id=str(intent_id),
            transaction_id=transaction_id,
            amount_paise=amount_paise,
            payment_status=status,
            metadata=metadata,
        )

        interview_id = intent.get("interview_id")
        if interview_id:
            cur.execute(
                "UPDATE payments SET interview_id = %s WHERE checkout_intent_id = %s",
                (interview_id, intent_id),
            )
            return str(interview_id)

        attempt_number = 1
        if intent.get("retake_from"):
            attempt_number = _compute_attempt_number(cur, user_id, resume_id, jd_id, question_set)

        new_interview_id = str(uuid.uuid4())
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
                intent.get("retake_from"),
                attempt_number,
            ),
        )

        question_ids = intent.get("question_ids") or []
        if isinstance(question_ids, str):
            question_ids = json.loads(question_ids)
        question_ids = [str(qid) for qid in question_ids]

        linked = _link_questions(cur, new_interview_id, question_ids)
        if linked == 0 and question_ids:
            linked = _fallback_link_questions(
                cur, new_interview_id, user_id, resume_id, jd_id, question_set
            )
        if linked == 0:
            logger.warning("No questions linked for interview %s intent %s", new_interview_id, intent_id)

        cur.execute(
            """
            UPDATE checkout_intents
            SET status = 'fulfilled', interview_id = %s, fulfilled_at = now()
            WHERE id = %s
            """,
            (new_interview_id, intent_id),
        )
        cur.execute(
            "UPDATE payments SET interview_id = %s WHERE checkout_intent_id = %s",
            (new_interview_id, intent_id),
        )
        return new_interview_id

    return run_transaction(_work)


def mark_checkout_failed(intent_id: str, payment_payload: dict[str, Any] | None = None) -> None:
    """Backward-compatible wrapper; prefer record_checkout_payment_failure."""
    if payment_payload is None:
        payment_payload = {"status": "failed", "payment_id": "", "metadata": {}}
    record_checkout_payment_failure(intent_id, payment_payload)


def acquire_webhook_event(cur, event_id: str, event_type: str, payload: dict) -> str:
    """
    Register webhook event and return action: 'process', 'skip_processed', or 'retry'.
    Must be called inside a transaction before fulfillment.
    """
    cur.execute(
        "SELECT status, received_at FROM webhook_events WHERE event_id = %s FOR UPDATE",
        (event_id,),
    )
    existing = cur.fetchone()
    if existing:
        if existing["status"] == "processed":
            return "skip_processed"
        if existing["status"] == "processing":
            age = (_utcnow() - existing["received_at"]).total_seconds()
            if age < STALE_PROCESSING_SECONDS:
                return "skip_processing"
            cur.execute(
                """
                UPDATE webhook_events
                SET status = 'failed', error_message = 'stale processing lock'
                WHERE event_id = %s
                """,
                (event_id,),
            )
        cur.execute(
            """
            UPDATE webhook_events
            SET status = 'processing', event_type = %s, payload = %s::jsonb,
                error_message = NULL, received_at = now()
            WHERE event_id = %s
            """,
            (event_type, json.dumps(payload), event_id),
        )
        return "process"

    cur.execute(
        """
        INSERT INTO webhook_events (event_id, event_type, status, payload)
        VALUES (%s, %s, 'processing', %s::jsonb)
        """,
        (event_id, event_type, json.dumps(payload)),
    )
    return "process"


def complete_webhook_event(event_id: str, success: bool, error_message: str | None = None) -> None:
    def _work(cur):
        cur.execute(
            """
            UPDATE webhook_events
            SET status = %s, processed_at = now(), error_message = %s
            WHERE event_id = %s
            """,
            ("processed" if success else "failed", error_message, event_id),
        )

    run_transaction(_work)


def resolve_intent_id_from_payload(payment_payload: dict[str, Any]) -> str | None:
    metadata = payment_payload.get("metadata") or {}
    intent_id = metadata.get("checkout_intent_id")
    return str(intent_id) if intent_id else None
