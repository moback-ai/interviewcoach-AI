"""HTTP handlers for Dodo checkout and webhooks."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from flask import jsonify, request

from common.db import execute, query_one, run_transaction
from common.dodo_client import (
    DodoClientError,
    checkout_amount_paise,
    checkout_expiry_minutes,
    create_checkout_session,
)
from common.dodo_webhook import (
    WebhookVerificationError,
    extract_payment_payload,
    parse_webhook_event,
    verify_webhook_signature,
)
from common.payment_fulfillment import (
    FulfillmentError,
    PaidNeedsReview,
    acquire_webhook_event,
    complete_webhook_event,
    fulfill_checkout_intent,
    mark_checkout_failed,
    resolve_intent_id_from_payload,
    snapshot_question_ids,
)
from common.rate_limit import user_rate_limit
from common.runtime_config import require_env

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _utcnow():
    return datetime.now(timezone.utc)


def _return_url(checkout_intent_id: str) -> str:
    base = require_env("DOMAIN").rstrip("/")
    return f"{base}/payment-status?checkout_intent_id={checkout_intent_id}"


def _validate_uuid(value: str, field: str) -> str | None:
    if not value or not _UUID_RE.match(str(value).strip()):
        return f"{field} must be a valid UUID"
    return None


def _verify_resume_jd_owned(user_id: str, resume_id: str, jd_id: str) -> bool:
    row = query_one(
        """
        SELECT 1
        FROM resumes r
        JOIN job_descriptions jd ON jd.id = %s AND jd.user_id = %s
        WHERE r.id = %s AND r.user_id = %s
        LIMIT 1
        """,
        (jd_id, user_id, resume_id, user_id),
    )
    return row is not None


def _verify_retake_from(user_id: str, retake_from: str) -> bool:
    row = query_one(
        """
        SELECT 1 FROM interviews
        WHERE id = %s AND user_id = %s
          AND status IN ('completed', 'ENDED')
        LIMIT 1
        """,
        (retake_from, user_id),
    )
    return row is not None


@user_rate_limit(max_calls=10, window_seconds=60)
def create_checkout_handler():
    if request.method == "OPTIONS":
        return jsonify({"message": "OK"}), 200

    data = request.get_json() or {}
    user_id = request.user["id"]
    resume_id = (data.get("resume_id") or "").strip()
    jd_id = (data.get("jd_id") or "").strip()
    question_set = data.get("question_set")
    retake_from = (data.get("retake_from") or "").strip() or None

    for field, value in (("resume_id", resume_id), ("jd_id", jd_id)):
        err = _validate_uuid(value, field)
        if err:
            return jsonify({"success": False, "message": err}), 400

    if question_set is None:
        return jsonify({"success": False, "message": "question_set is required"}), 400
    try:
        question_set = int(question_set)
    except (TypeError, ValueError):
        return jsonify({"success": False, "message": "question_set must be an integer"}), 400

    if retake_from:
        err = _validate_uuid(retake_from, "retake_from")
        if err:
            return jsonify({"success": False, "message": err}), 400
        if not _verify_retake_from(user_id, retake_from):
            return jsonify({"success": False, "message": "Invalid retake_from interview"}), 400

    if not _verify_resume_jd_owned(user_id, resume_id, jd_id):
        return jsonify({"success": False, "message": "Resume or job description not found"}), 404

    amount_paise = checkout_amount_paise()
    expiry_minutes = checkout_expiry_minutes()
    intent_id = str(uuid.uuid4())
    expires_at = _utcnow() + timedelta(minutes=expiry_minutes)

    def _create_intent(cur):
        question_ids = snapshot_question_ids(cur, user_id, resume_id, jd_id, question_set)
        cur.execute(
            """
            INSERT INTO checkout_intents (
                id, user_id, resume_id, jd_id, question_set, retake_from,
                status, amount_paise, expires_at, question_ids
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                intent_id,
                user_id,
                resume_id,
                jd_id,
                question_set,
                retake_from,
                amount_paise,
                expires_at,
                json.dumps(question_ids),
            ),
        )

    run_transaction(_create_intent)

    user = query_one(
        "SELECT email, full_name FROM users WHERE id = %s",
        (user_id,),
    )
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    try:
        session = create_checkout_session(
            checkout_intent_id=intent_id,
            user_id=user_id,
            user_email=user["email"],
            user_name=user.get("full_name") or "",
            resume_id=resume_id,
            jd_id=jd_id,
            question_set=question_set,
            retake_from=retake_from,
            return_url=_return_url(intent_id),
        )
    except DodoClientError as exc:
        execute("DELETE FROM checkout_intents WHERE id = %s AND status = 'pending'", (intent_id,))
        logger.exception("Dodo checkout session failed for intent %s", intent_id)
        return jsonify({"success": False, "message": str(exc)}), 502

    if session.get("session_id"):
        execute(
            "UPDATE checkout_intents SET dodo_session_id = %s WHERE id = %s",
            (session["session_id"], intent_id),
        )

    return jsonify({
        "success": True,
        "checkout_url": session["checkout_url"],
        "payment_url": session["checkout_url"],
        "checkout_intent_id": intent_id,
    }), 201


def checkout_status_handler(intent_id: str):
    err = _validate_uuid(intent_id, "checkout_intent_id")
    if err:
        return jsonify({"success": False, "message": err}), 400

    intent = query_one(
        "SELECT * FROM checkout_intents WHERE id = %s AND user_id = %s",
        (intent_id, request.user["id"]),
    )
    if not intent:
        return jsonify({"success": False, "message": "Checkout intent not found"}), 404

    payment = query_one(
        "SELECT payment_status, transaction_id, amount FROM payments WHERE checkout_intent_id = %s",
        (intent_id,),
    )

    status = intent["status"]
    response = {
        "success": True,
        "status": status,
        "checkout_intent_id": str(intent["id"]),
        "interview_id": str(intent["interview_id"]) if intent.get("interview_id") else None,
        "resume_id": str(intent["resume_id"]),
        "jd_id": str(intent["jd_id"]),
        "question_set": intent["question_set"],
    }
    if payment:
        response["payment_status"] = payment["payment_status"]
        response["transaction_id"] = payment["transaction_id"]
        response["amount"] = int(payment["amount"]) if payment.get("amount") is not None else None

    return jsonify(response), 200


def dodo_webhook_handler():
    if request.method == "OPTIONS":
        return jsonify({"message": "OK"}), 200

    raw_body = request.get_data(cache=True)
    headers = {k: v for k, v in request.headers.items()}

    try:
        verify_webhook_signature(headers, raw_body)
        event = parse_webhook_event(raw_body)
    except WebhookVerificationError as exc:
        logger.warning("Webhook verification failed: %s", exc)
        return jsonify({"error": str(exc)}), 401

    payment_payload = extract_payment_payload(event)
    event_id = payment_payload.get("event_id") or ""
    event_type = payment_payload.get("event_type") or ""
    if not event_id:
        fallback = payment_payload.get("payment_id") or "unknown"
        event_id = f"{event_type}:{fallback}"

    if not event_type.startswith("payment."):
        return jsonify({"success": True, "message": "ignored", "event_type": event_type}), 200

    intent_id = resolve_intent_id_from_payload(payment_payload)

    def _register(cur):
        return acquire_webhook_event(cur, event_id, event_type, event)

    try:
        action = run_transaction(_register)
    except Exception:
        logger.exception("Failed to register webhook event %s", event_id)
        return jsonify({"error": "webhook registration failed"}), 500

    if action == "skip_processed":
        return jsonify({"success": True, "message": "already processed"}), 200
    if action == "skip_processing":
        return jsonify({"error": "event processing in progress"}), 503

    if not intent_id:
        complete_webhook_event(event_id, False, "missing checkout_intent_id in metadata")
        return jsonify({"error": "missing checkout_intent_id"}), 400

    try:
        status = (payment_payload.get("status") or "").lower()
        if status in {"failed", "cancelled", "canceled"}:
            mark_checkout_failed(intent_id)
            complete_webhook_event(event_id, True)
            return jsonify({"success": True, "message": "payment failure recorded"}), 200

        interview_id = fulfill_checkout_intent(intent_id, payment_payload)
        complete_webhook_event(event_id, True)
        return jsonify({
            "success": True,
            "message": "fulfilled" if interview_id else "acknowledged",
            "interview_id": interview_id,
        }), 200
    except PaidNeedsReview as exc:
        logger.error("Paid needs review for intent %s: %s", intent_id, exc)
        complete_webhook_event(event_id, True, str(exc))
        return jsonify({"success": True, "message": "paid_needs_review"}), 200
    except (FulfillmentError, Exception) as exc:
        logger.exception("Webhook fulfillment failed for intent %s", intent_id)
        complete_webhook_event(event_id, False, str(exc))
        return jsonify({"error": "fulfillment failed"}), 500
