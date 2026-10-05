"""HTTP handlers for free-tier interview start and quota."""

from __future__ import annotations

from flask import jsonify, request

from common.db import query_one

from common.interview_start import (
    InterviewStartError,
    PaymentRequiredError,
    create_started_interview,
    interview_quota,
)
from common.payment_handlers import (
    _validate_uuid,
    _verify_resume_jd_owned,
    _verify_retake_from,
)


def interview_quota_handler():
    if request.method == "OPTIONS":
        return jsonify({"message": "OK"}), 200
    quota = interview_quota(request.user["id"])
    return jsonify({"success": True, "data": quota}), 200


def start_interview_handler():
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

    active_row = query_one(
        """
        SELECT id FROM interviews
        WHERE user_id = %s AND resume_id = %s AND jd_id = %s AND question_set = %s
          AND status IN ('STARTED', 'ACTIVE')
        LIMIT 1
        """,
        (user_id, resume_id, jd_id, question_set),
    )
    if active_row:
        return jsonify({
            "success": False,
            "active_interview_id": str(active_row["id"]),
            "message": "You already have an active interview in progress for this question set. Please resume your existing interview before starting a new retake.",
        }), 400

    quota = interview_quota(user_id)
    if quota["payment_required"]:
        return jsonify({
            "success": False,
            "payment_required": True,
            "message": "Payment is required to start another interview.",
            "data": quota,
        }), 402

    try:
        interview_id = create_started_interview(
            user_id,
            resume_id,
            jd_id,
            question_set,
            retake_from=retake_from,
        )
    except InterviewStartError as exc:
        return jsonify({"success": False, "message": str(exc)}), 400

    return jsonify({
        "success": True,
        "interview_id": interview_id,
        "data": {"interview_id": interview_id},
    }), 201
