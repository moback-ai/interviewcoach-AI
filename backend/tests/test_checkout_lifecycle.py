"""Unit tests for checkout lifecycle: expiry, failures, idempotency, auth."""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from common.payment_fulfillment import (
    FAILURE_STATUSES,
    TERMINAL_SUCCESS_STATUSES,
    _failure_reason_from_status,
    _is_success_payment_status,
    _record_checkout_payment_failure_cur,
    expire_checkout_intent_if_stale,
    mark_checkout_creation_failed,
    record_checkout_payment_failure,
)
from common.payment_handlers import checkout_status_handler


def _utcnow():
    return datetime.now(timezone.utc)


INTENT_ID = "11111111-1111-4111-8111-111111111111"
USER_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
USER_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


class FakeCursor:
  def __init__(self):
    self.intents: dict[str, dict] = {}
    self.payments: dict[str, dict] = {}
    self.executed: list[tuple] = []
    self._fetch_result = None
    self._fetchall_result: list = []

  def execute(self, sql, params=None):
    self.executed.append((sql, params))
    normalized = " ".join(sql.split()).lower()

    if "from checkout_intents where id = %s for update" in normalized:
      intent_id = params[0]
      row = self.intents.get(intent_id)
      self._fetch_result = dict(row) if row else None
      return

    if "select transaction_id from payments where checkout_intent_id" in normalized:
      intent_id = params[0]
      for pay in self.payments.values():
        if pay.get("checkout_intent_id") == intent_id:
          self._fetch_result = {"transaction_id": pay["transaction_id"]}
          return
      self._fetch_result = None
      return

    if "update checkout_intents" in normalized and "set status = 'failed'" in normalized:
      intent_id = params[1]
      if intent_id in self.intents:
        self.intents[intent_id]["status"] = "failed"
        self.intents[intent_id]["failure_reason"] = params[0]
      return

    if "update checkout_intents" in normalized and "set status = 'expired'" in normalized:
      intent_id = params[0]
      if intent_id in self.intents:
        if (
          self.intents[intent_id]["status"] == "pending"
          and self.intents[intent_id]["expires_at"] < _utcnow()
        ):
          self.intents[intent_id]["status"] = "expired"
          self.intents[intent_id]["failure_reason"] = "abandoned"
          self._fetch_result = {"id": intent_id}
        else:
          self._fetch_result = None
      return

    if "insert into payments" in normalized:
      (
        user_id,
        checkout_intent_id,
        _amount,
        payment_status,
        transaction_id,
        _metadata,
        is_success,
      ) = params
      self.payments[transaction_id] = {
        "user_id": user_id,
        "checkout_intent_id": checkout_intent_id,
        "payment_status": payment_status,
        "transaction_id": transaction_id,
        "paid_at": _utcnow() if is_success else None,
        "recorded_at": _utcnow(),
      }
      return

    if "returning id" in normalized:
      self._fetchall_result = [{"id": INTENT_ID}]
      return

    self._fetch_result = None

  def fetchone(self):
    return self._fetch_result

  def fetchall(self):
    return self._fetchall_result


def _pending_intent(*, status="pending", expires_at=None, failure_reason=None):
  return {
    "id": INTENT_ID,
    "user_id": USER_A,
    "status": status,
    "failure_reason": failure_reason,
    "expires_at": expires_at or (_utcnow() + timedelta(minutes=30)),
    "resume_id": "22222222-2222-4222-8222-222222222222",
    "jd_id": "33333333-3333-4333-8333-333333333333",
    "question_set": 1,
    "question_ids": [],
    "interview_id": None,
  }


class TestCheckoutLifecycleHelpers(unittest.TestCase):
  def test_failure_reason_from_status(self):
    self.assertEqual(_failure_reason_from_status("cancelled"), "provider_cancelled")
    self.assertEqual(_failure_reason_from_status("failed"), "provider_failed")

  def test_is_success_payment_status(self):
    self.assertTrue(_is_success_payment_status("succeeded"))
    self.assertFalse(_is_success_payment_status("failed"))


class TestRecordCheckoutPaymentFailure(unittest.TestCase):
  def test_failed_webhook_with_payment_id(self):
    cur = FakeCursor()
    cur.intents[INTENT_ID] = _pending_intent()
    payload = {
      "status": "failed",
      "payment_id": "pay_123",
      "amount_paise": 200,
      "metadata": {},
    }
    changed = _record_checkout_payment_failure_cur(cur, INTENT_ID, payload)
    self.assertTrue(changed)
    self.assertEqual(cur.intents[INTENT_ID]["status"], "failed")
    self.assertEqual(cur.intents[INTENT_ID]["failure_reason"], "provider_failed")
    self.assertIn("pay_123", cur.payments)

  def test_cancelled_webhook(self):
    cur = FakeCursor()
    cur.intents[INTENT_ID] = _pending_intent()
    payload = {"status": "cancelled", "payment_id": "", "metadata": {}}
    changed = _record_checkout_payment_failure_cur(cur, INTENT_ID, payload)
    self.assertTrue(changed)
    self.assertEqual(cur.intents[INTENT_ID]["failure_reason"], "provider_cancelled")
    self.assertEqual(len(cur.payments), 0)

  def test_failure_without_payment_id(self):
    cur = FakeCursor()
    cur.intents[INTENT_ID] = _pending_intent()
    payload = {"status": "failed", "payment_id": "", "metadata": {}}
    _record_checkout_payment_failure_cur(cur, INTENT_ID, payload)
    self.assertEqual(cur.intents[INTENT_ID]["status"], "failed")
    self.assertEqual(len(cur.payments), 0)

  def test_idempotent_replay_same_payment_id(self):
    cur = FakeCursor()
    cur.intents[INTENT_ID] = _pending_intent(status="failed", failure_reason="provider_failed")
    cur.payments["pay_123"] = {
      "checkout_intent_id": INTENT_ID,
      "transaction_id": "pay_123",
    }
    payload = {"status": "failed", "payment_id": "pay_123", "metadata": {}}
    changed = _record_checkout_payment_failure_cur(cur, INTENT_ID, payload)
    self.assertFalse(changed)

  def test_no_downgrade_fulfilled(self):
    cur = FakeCursor()
    cur.intents[INTENT_ID] = _pending_intent(status="fulfilled")
    cur.intents[INTENT_ID]["interview_id"] = "44444444-4444-4444-8444-444444444444"
    payload = {"status": "failed", "payment_id": "pay_999", "metadata": {}}
    changed = _record_checkout_payment_failure_cur(cur, INTENT_ID, payload)
    self.assertFalse(changed)
    self.assertEqual(cur.intents[INTENT_ID]["status"], "fulfilled")

  def test_expired_to_failed(self):
    cur = FakeCursor()
    cur.intents[INTENT_ID] = _pending_intent(
      status="expired",
      expires_at=_utcnow() - timedelta(minutes=5),
      failure_reason="abandoned",
    )
    payload = {"status": "failed", "payment_id": "pay_late", "metadata": {}}
    changed = _record_checkout_payment_failure_cur(cur, INTENT_ID, payload)
    self.assertTrue(changed)
    self.assertEqual(cur.intents[INTENT_ID]["status"], "failed")


class TestExpiry(unittest.TestCase):
  @patch("common.payment_fulfillment.run_transaction")
  def test_expire_stale_intent(self, mock_run_transaction):
    def _run(fn):
      cur = FakeCursor()
      cur.intents[INTENT_ID] = _pending_intent(
        expires_at=_utcnow() - timedelta(minutes=1),
      )
      return fn(cur)

    mock_run_transaction.side_effect = _run
    result = expire_checkout_intent_if_stale(INTENT_ID)
    self.assertTrue(result)


class TestCheckoutCreationFailure(unittest.TestCase):
  @patch("common.payment_fulfillment.run_transaction")
  def test_mark_checkout_creation_failed(self, mock_run_transaction):
    captured = {}

    def _run(fn):
      cur = MagicMock()
      fn(cur)
      return None

    mock_run_transaction.side_effect = _run
    mark_checkout_creation_failed(INTENT_ID, http_status=502, error_kind="dodo_checkout_api")
    mock_run_transaction.assert_called_once()


class TestCheckoutStatusAuth(unittest.TestCase):
  @patch("common.payment_handlers.query_one")
  @patch("common.payment_handlers.expire_checkout_intent_if_stale")
  def test_cross_user_poll_returns_404(self, _mock_expire, mock_query_one):
    mock_query_one.return_value = None
    request = MagicMock()
    request.user = {"id": USER_B}
    with patch("common.payment_handlers.request", request):
      with patch("common.payment_handlers.jsonify", side_effect=lambda x: x):
        response, status_code = checkout_status_handler(INTENT_ID)
    self.assertEqual(status_code, 404)
    self.assertFalse(response["success"])

  @patch("common.payment_handlers.query_one")
  @patch("common.payment_handlers.expire_checkout_intent_if_stale")
  def test_owner_polls_failed_status(self, _mock_expire, mock_query_one):
    mock_query_one.side_effect = [
      {**_pending_intent(status="failed"), "id": INTENT_ID},
      None,
    ]
    request = MagicMock()
    request.user = {"id": USER_A}
    with patch("common.payment_handlers.request", request):
      with patch("common.payment_handlers.jsonify", side_effect=lambda x: x):
        response, status_code = checkout_status_handler(INTENT_ID)
    self.assertEqual(status_code, 200)
    self.assertEqual(response["status"], "failed")


class TestRecordCheckoutPaymentFailureWrapper(unittest.TestCase):
  @patch("common.payment_fulfillment.run_transaction")
  def test_wrapper_returns_bool(self, mock_run_transaction):
    mock_run_transaction.return_value = True
    result = record_checkout_payment_failure(
      INTENT_ID,
      {"status": "failed", "payment_id": "pay_1", "metadata": {}},
    )
    self.assertTrue(result)


if __name__ == "__main__":
  unittest.main()
