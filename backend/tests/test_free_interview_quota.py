"""Tests for free interview quota and start endpoints."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

import common.runtime_config as runtime_config

runtime_config._LOADED = True
runtime_config._CONFIG = {
    "JWT_SECRET": "test-jwt-secret-for-pytest-only-32chars",
    "DOMAIN": "http://localhost:5173",
    "FREE_INTERVIEW_LIMIT": "2",
    "DODO_PAYMENTS_API_KEY": "test-key",
    "DODO_PRODUCT_ID": "pdt_test",
}

from common.interview_handlers import interview_quota_handler, start_interview_handler
from common.interview_start import (
    STARTED_INTERVIEW_STATUSES,
    count_started_interviews,
    create_started_interview_cur,
    interview_quota,
)
from common.payment_handlers import create_checkout_handler

USER_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
RESUME_ID = "22222222-2222-4222-8222-222222222222"
JD_ID = "33333333-3333-4333-8333-333333333333"
INTERVIEW_ID = "44444444-4444-4444-8444-444444444444"


class FakeInterviewCursor:
    def __init__(self):
        self.executed: list[tuple] = []
        self._fetchone = None
        self.rowcount = 0

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        normalized = " ".join(sql.split()).lower()
        if "insert into interviews" in normalized:
            self._fetchone = {"id": INTERVIEW_ID}
        elif "from interviews" in normalized and "count" in normalized:
            pass
        elif "update interview_questions" in normalized or "insert into interview_questions" in normalized:
            self.rowcount = 3

    def fetchone(self):
        return self._fetchone


class TestInterviewQuotaHelpers(unittest.TestCase):
  @patch("common.interview_start.query_one")
  def test_count_started_interviews_uses_started_statuses(self, mock_query_one):
    mock_query_one.return_value = {"cnt": 2}
    count = count_started_interviews(USER_A)
    self.assertEqual(count, 2)
    mock_query_one.assert_called_once()
    _sql, params = mock_query_one.call_args[0]
    self.assertEqual(params[0], USER_A)
    self.assertEqual(set(params[1]), set(STARTED_INTERVIEW_STATUSES))

  @patch("common.interview_start.count_started_interviews", return_value=2)
  def test_payment_required_at_limit(self, _mock_count):
    quota = interview_quota(USER_A)
    self.assertTrue(quota["payment_required"])
    self.assertEqual(quota["free_remaining"], 0)
    self.assertEqual(quota["free_limit"], 2)

  @patch("common.interview_start.count_started_interviews", return_value=1)
  def test_free_remaining_under_limit(self, _mock_count):
    quota = interview_quota(USER_A)
    self.assertFalse(quota["payment_required"])
    self.assertEqual(quota["free_remaining"], 1)


class TestInterviewHandlers(unittest.TestCase):
  def setUp(self):
    self.app = Flask(__name__)

  @patch("common.interview_handlers.create_started_interview", return_value=INTERVIEW_ID)
  @patch("common.interview_handlers.interview_quota")
  @patch("common.interview_handlers._verify_resume_jd_owned", return_value=True)
  def test_start_interview_returns_201_when_under_quota(
    self, _mock_owned, mock_quota, mock_create
  ):
    mock_quota.return_value = {
      "started_count": 0,
      "free_limit": 2,
      "free_remaining": 2,
      "payment_required": False,
    }
    with self.app.test_request_context(
      "/api/interviews/start",
      method="POST",
      json={
        "resume_id": RESUME_ID,
        "jd_id": JD_ID,
        "question_set": 1,
      },
    ):
      from flask import request

      request.user = {"id": USER_A}
      response, status = start_interview_handler()
      payload = json.loads(response.get_data(as_text=True))
    self.assertEqual(status, 201)
    self.assertTrue(payload["success"])
    self.assertEqual(payload["interview_id"], INTERVIEW_ID)
    mock_create.assert_called_once()

  @patch("common.interview_handlers.create_started_interview")
  @patch("common.interview_handlers.interview_quota")
  @patch("common.interview_handlers._verify_resume_jd_owned", return_value=True)
  def test_start_interview_returns_402_at_quota(
    self, _mock_owned, mock_quota, mock_create
  ):
    mock_quota.return_value = {
      "started_count": 2,
      "free_limit": 2,
      "free_remaining": 0,
      "payment_required": True,
    }
    with self.app.test_request_context(
      "/api/interviews/start",
      method="POST",
      json={
        "resume_id": RESUME_ID,
        "jd_id": JD_ID,
        "question_set": 1,
      },
    ):
      from flask import request

      request.user = {"id": USER_A}
      response, status = start_interview_handler()
      payload = json.loads(response.get_data(as_text=True))
    self.assertEqual(status, 402)
    self.assertTrue(payload["payment_required"])
    mock_create.assert_not_called()

  @patch("common.interview_handlers.interview_quota")
  def test_interview_quota_handler(self, mock_quota):
    mock_quota.return_value = {
      "started_count": 1,
      "free_limit": 2,
      "free_remaining": 1,
      "payment_required": False,
    }
    with self.app.test_request_context("/api/interview-quota", method="GET"):
      from flask import request

      request.user = {"id": USER_A}
      response, status = interview_quota_handler()
      payload = json.loads(response.get_data(as_text=True))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["free_remaining"], 1)


class TestCheckoutGuard(unittest.TestCase):
  def setUp(self):
    self.app = Flask(__name__)

  @patch("common.interview_start.interview_quota")
  @patch("common.payment_handlers._verify_resume_jd_owned", return_value=True)
  def test_create_checkout_rejected_when_free_slot_available(
    self, _mock_owned, mock_quota
  ):
    mock_quota.return_value = {
      "started_count": 0,
      "free_limit": 2,
      "free_remaining": 2,
      "payment_required": False,
    }
    with self.app.test_request_context(
      "/api/checkout",
      method="POST",
      json={
        "resume_id": RESUME_ID,
        "jd_id": JD_ID,
        "question_set": 1,
      },
    ):
      from flask import request

      request.user = {"id": USER_A}
      response, status = create_checkout_handler()
      payload = json.loads(response.get_data(as_text=True))
    self.assertEqual(status, 400)
    self.assertIn("/api/interviews/start", payload["message"])


class TestCreateStartedInterview(unittest.TestCase):
  @patch("common.interview_start._fallback_link_questions", return_value=0)
  @patch("common.interview_start._link_questions", return_value=3)
  @patch("common.interview_start.snapshot_question_ids", return_value=["q1", "q2", "q3"])
  @patch("common.interview_start._verify_ownership", return_value=True)
  @patch("common.interview_start._compute_attempt_number", return_value=1)
  def test_create_started_interview_links_questions(
    self,
    _mock_attempt,
    _mock_owned,
    mock_snapshot,
    mock_link,
    _mock_fallback,
  ):
    cur = FakeInterviewCursor()
    interview_id = create_started_interview_cur(
      cur, USER_A, RESUME_ID, JD_ID, 1
    )
    self.assertTrue(interview_id)
    mock_snapshot.assert_called_once()
    mock_link.assert_called_once()
    insert_calls = [
      sql for sql, _ in cur.executed if "insert into interviews" in sql.lower()
    ]
    self.assertEqual(len(insert_calls), 1)


if __name__ == "__main__":
  unittest.main()
