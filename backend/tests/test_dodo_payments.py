"""Unit tests for Dodo webhook verification and payment helpers."""

import base64
import hashlib
import hmac
import json
import time
import unittest
from unittest.mock import patch

from common.dodo_webhook import (
    WebhookVerificationError,
    extract_payment_payload,
    verify_webhook_signature,
    _extract_v1_signature,
)
from common.payment_fulfillment import resolve_intent_id_from_payload


class TestDodoWebhook(unittest.TestCase):
    def setUp(self):
        self.test_secret = base64.b64encode(b"test-secret-key-32bytes-long!!").decode()
        self.secret_patcher = patch(
            "common.dodo_webhook.require_env",
            return_value=f"whsec_{self.test_secret}",
        )
        self.secret_patcher.start()

    def tearDown(self):
        self.secret_patcher.stop()

    def _sign(self, secret: str, webhook_id: str, timestamp: str, body: bytes) -> str:
        cleaned = secret.removeprefix("whsec_")
        key_bytes = base64.b64decode(cleaned)
        signed = f"{webhook_id}.{timestamp}.{body.decode('utf-8')}"
        digest = hmac.new(key_bytes, signed.encode("utf-8"), hashlib.sha256).digest()
        return f"v1={base64.b64encode(digest).decode('utf-8')}"

    def test_extract_v1_signature_formats(self):
        self.assertEqual(_extract_v1_signature("v1=abc123"), "abc123")
        self.assertEqual(_extract_v1_signature("v1,abc123"), "abc123")

    def test_verify_webhook_signature_valid(self):
        body = b'{"id":"evt_1","type":"payment.succeeded"}'
        webhook_id = "msg_123"
        timestamp = str(int(time.time()))
        headers = {
            "webhook-id": webhook_id,
            "webhook-timestamp": timestamp,
            "webhook-signature": self._sign(f"whsec_{self.test_secret}", webhook_id, timestamp, body),
        }
        verify_webhook_signature(headers, body)

    def test_verify_webhook_signature_rejects_invalid(self):
        body = b'{"id":"evt_1"}'
        headers = {
            "webhook-id": "msg_123",
            "webhook-timestamp": str(int(time.time())),
            "webhook-signature": "v1=invalid",
        }
        with self.assertRaises(WebhookVerificationError):
            verify_webhook_signature(headers, body)

    def test_extract_payment_payload_metadata(self):
        event = {
            "id": "evt_abc",
            "type": "payment.succeeded",
            "data": {
                "payment_id": "pay_123",
                "status": "succeeded",
                "total_amount": 49900,
                "metadata": {"checkout_intent_id": "11111111-1111-4111-8111-111111111111"},
            },
        }
        payload = extract_payment_payload(event)
        self.assertEqual(payload["event_id"], "evt_abc")
        self.assertEqual(payload["payment_id"], "pay_123")
        self.assertEqual(payload["amount_paise"], 49900)

    def test_resolve_intent_id_from_payload(self):
        payload = {
            "metadata": {
                "checkout_intent_id": "22222222-2222-4222-8222-222222222222",
            }
        }
        self.assertEqual(
            resolve_intent_id_from_payload(payload),
            "22222222-2222-4222-8222-222222222222",
        )


if __name__ == "__main__":
    unittest.main()
