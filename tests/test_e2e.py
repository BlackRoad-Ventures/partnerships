"""
BlackRoad Ventures — End-to-End Tests
======================================
Full integration tests covering:
- Stripe payment flows (create → webhook → verify)
- Partnership + Stripe combined flows
- Pi routing with event delivery
- Webhook signature verification
- Subscription lifecycle
- Error handling and edge cases

These tests use local SQLite databases and mock HTTP calls
so they run without network access or Stripe API keys.
"""

import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from stripe_integration import (
    PaymentStore,
    StripeAPIError,
    StripeClient,
    WebhookProcessor,
    PartnershipPaymentManager,
)
from pi_router import PiEndpointStore, PiRouter, _send_to_endpoint
from partnerships import init_db, STATUSES
from startup_metrics import StartupMetricsManager


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def tmp_db(tmp_path):
    return tmp_path / "test.db"


@pytest.fixture
def payment_store(tmp_path):
    store = PaymentStore(tmp_path / "payments.db")
    yield store
    store.close()


@pytest.fixture
def pi_store(tmp_path):
    store = PiEndpointStore(tmp_path / "pi_router.db")
    yield store
    store.close()


@pytest.fixture
def pi_router(tmp_path):
    router = PiRouter(tmp_path / "pi_router.db")
    yield router
    router.close()


@pytest.fixture
def startup_mgr(tmp_path):
    mgr = StartupMetricsManager(tmp_path / "startups.db")
    yield mgr
    mgr.close()


@pytest.fixture
def webhook_processor(payment_store):
    return WebhookProcessor(payment_store)


@pytest.fixture
def mock_stripe_client():
    """A StripeClient with mocked HTTP calls."""
    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake_key_for_testing"}):
        client = StripeClient()
    client._request = MagicMock()
    return client


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Payment Store Operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestPaymentStoreE2E:
    """Test the full payment recording lifecycle."""

    def test_record_and_retrieve_payment(self, payment_store):
        payment_store.record_payment(
            stripe_payment_id="pi_test_001",
            partner="Acme Corp",
            amount_cents=500_00,
            currency="usd",
            status="requires_payment_method",
            description="Partnership Q1",
        )

        payment = payment_store.get_payment("pi_test_001")
        assert payment is not None
        assert payment["partner"] == "Acme Corp"
        assert payment["amount_cents"] == 50000
        assert payment["status"] == "requires_payment_method"

    def test_update_payment_status_lifecycle(self, payment_store):
        """Test payment going through: pending → succeeded."""
        payment_store.record_payment(
            stripe_payment_id="pi_lifecycle_001",
            partner="TechCorp",
            amount_cents=100_00,
            status="pending",
        )

        # Transition to succeeded
        updated = payment_store.update_payment_status(
            "pi_lifecycle_001", "succeeded"
        )
        assert updated is True

        payment = payment_store.get_payment("pi_lifecycle_001")
        assert payment["status"] == "succeeded"

    def test_list_payments_by_partner(self, payment_store):
        for i in range(3):
            payment_store.record_payment(
                stripe_payment_id=f"pi_partner_{i}",
                partner="AlphaVentures",
                amount_cents=(i + 1) * 10000,
            )
        payment_store.record_payment(
            stripe_payment_id="pi_other_001",
            partner="BetaCorp",
            amount_cents=5000,
        )

        alpha_payments = payment_store.list_payments(partner="AlphaVentures")
        assert len(alpha_payments) == 3

        all_payments = payment_store.list_payments()
        assert len(all_payments) == 4

    def test_list_payments_by_status(self, payment_store):
        payment_store.record_payment(
            stripe_payment_id="pi_s1", partner="A", amount_cents=100, status="succeeded",
        )
        payment_store.record_payment(
            stripe_payment_id="pi_s2", partner="B", amount_cents=200, status="failed",
        )
        payment_store.record_payment(
            stripe_payment_id="pi_s3", partner="C", amount_cents=300, status="succeeded",
        )

        succeeded = payment_store.list_payments(status="succeeded")
        assert len(succeeded) == 2

        failed = payment_store.list_payments(status="failed")
        assert len(failed) == 1

    def test_update_nonexistent_payment(self, payment_store):
        result = payment_store.update_payment_status("pi_nonexistent", "succeeded")
        assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Subscription Store Operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestSubscriptionStoreE2E:
    def test_record_and_retrieve_subscription(self, payment_store):
        payment_store.record_subscription(
            stripe_subscription_id="sub_test_001",
            stripe_customer_id="cus_test_001",
            partner="CloudSync",
            price_id="price_monthly_500",
            status="active",
        )

        sub = payment_store.get_subscription("sub_test_001")
        assert sub is not None
        assert sub["partner"] == "CloudSync"
        assert sub["status"] == "active"

    def test_subscription_lifecycle(self, payment_store):
        """Test subscription: incomplete → active → past_due → canceled."""
        payment_store.record_subscription(
            stripe_subscription_id="sub_lifecycle",
            stripe_customer_id="cus_lc",
            partner="LifecycleCo",
            price_id="price_test",
            status="incomplete",
        )

        # Activate
        payment_store.update_subscription_status("sub_lifecycle", "active")
        sub = payment_store.get_subscription("sub_lifecycle")
        assert sub["status"] == "active"

        # Past due
        payment_store.update_subscription_status("sub_lifecycle", "past_due")
        sub = payment_store.get_subscription("sub_lifecycle")
        assert sub["status"] == "past_due"

        # Cancel
        payment_store.update_subscription_status("sub_lifecycle", "canceled")
        sub = payment_store.get_subscription("sub_lifecycle")
        assert sub["status"] == "canceled"

    def test_list_subscriptions_by_partner(self, payment_store):
        for i in range(2):
            payment_store.record_subscription(
                stripe_subscription_id=f"sub_p_{i}",
                stripe_customer_id=f"cus_p_{i}",
                partner="MultiSubCo",
                price_id=f"price_{i}",
            )

        subs = payment_store.list_subscriptions(partner="MultiSubCo")
        assert len(subs) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Webhook Processing
# ═══════════════════════════════════════════════════════════════════════════════


class TestWebhookProcessorE2E:
    """Test complete webhook event flows."""

    def _make_event(self, event_type, obj, event_id=None):
        return {
            "id": event_id or f"evt_{event_type.replace('.', '_')}_{int(time.time())}",
            "type": event_type,
            "data": {"object": obj},
        }

    def test_payment_succeeded_flow(self, payment_store, webhook_processor):
        """Full flow: record payment → receive webhook → verify status update."""
        # Step 1: Record initial payment
        payment_store.record_payment(
            stripe_payment_id="pi_webhook_001",
            partner="WebhookTestCo",
            amount_cents=250_00,
            status="requires_payment_method",
        )

        # Step 2: Process webhook
        event = self._make_event(
            "payment_intent.succeeded",
            {"id": "pi_webhook_001", "amount": 25000},
        )
        result = webhook_processor.process_event(event)

        assert result["status"] == "processed"
        assert result["action"] == "payment_confirmed"
        assert result["amount"] == 25000

        # Step 3: Verify status was updated
        payment = payment_store.get_payment("pi_webhook_001")
        assert payment["status"] == "succeeded"

    def test_payment_failed_flow(self, payment_store, webhook_processor):
        payment_store.record_payment(
            stripe_payment_id="pi_fail_001",
            partner="FailTestCo",
            amount_cents=100_00,
            status="processing",
        )

        event = self._make_event(
            "payment_intent.payment_failed",
            {
                "id": "pi_fail_001",
                "last_payment_error": {"message": "Card declined"},
            },
        )
        result = webhook_processor.process_event(event)

        assert result["status"] == "processed"
        assert result["action"] == "payment_failed"
        assert result["failure_message"] == "Card declined"

        payment = payment_store.get_payment("pi_fail_001")
        assert payment["status"] == "failed"

    def test_subscription_created_webhook(self, payment_store, webhook_processor):
        event = self._make_event(
            "customer.subscription.created",
            {
                "id": "sub_wh_001",
                "customer": "cus_wh_001",
                "status": "active",
                "items": {
                    "data": [{"price": {"id": "price_wh_monthly"}}]
                },
                "metadata": {"partner": "WebhookSubCo"},
            },
        )
        result = webhook_processor.process_event(event)

        assert result["status"] == "processed"
        assert result["action"] == "subscription_created"

        sub = payment_store.get_subscription("sub_wh_001")
        assert sub is not None
        assert sub["partner"] == "WebhookSubCo"

    def test_invoice_paid_activates_subscription(
        self, payment_store, webhook_processor
    ):
        """Invoice paid → subscription should become active."""
        payment_store.record_subscription(
            stripe_subscription_id="sub_inv_001",
            stripe_customer_id="cus_inv",
            partner="InvoiceCo",
            price_id="price_inv",
            status="incomplete",
        )

        event = self._make_event(
            "invoice.paid",
            {
                "id": "inv_001",
                "subscription": "sub_inv_001",
                "amount_paid": 5000,
            },
        )
        result = webhook_processor.process_event(event)

        assert result["action"] == "invoice_paid"
        sub = payment_store.get_subscription("sub_inv_001")
        assert sub["status"] == "active"

    def test_invoice_failed_sets_past_due(
        self, payment_store, webhook_processor
    ):
        payment_store.record_subscription(
            stripe_subscription_id="sub_pastdue",
            stripe_customer_id="cus_pd",
            partner="PastDueCo",
            price_id="price_pd",
            status="active",
        )

        event = self._make_event(
            "invoice.payment_failed",
            {"id": "inv_fail_001", "subscription": "sub_pastdue"},
        )
        result = webhook_processor.process_event(event)

        assert result["action"] == "invoice_payment_failed"
        sub = payment_store.get_subscription("sub_pastdue")
        assert sub["status"] == "past_due"

    def test_idempotency_skips_duplicate_events(
        self, payment_store, webhook_processor
    ):
        """Same event ID processed twice → second is skipped."""
        event = self._make_event(
            "payment_intent.succeeded",
            {"id": "pi_idempotent", "amount": 1000},
            event_id="evt_idempotent_test",
        )

        result1 = webhook_processor.process_event(event)
        assert result1["status"] == "processed"

        result2 = webhook_processor.process_event(event)
        assert result2["status"] == "skipped"
        assert result2["reason"] == "already_processed"

    def test_unhandled_event_type_ignored(self, webhook_processor):
        event = self._make_event(
            "charge.dispute.created",
            {"id": "dp_001"},
        )
        result = webhook_processor.process_event(event)
        assert result["status"] == "ignored"

    def test_webhook_with_pi_callback(self, payment_store):
        """Verify Pi callback is invoked on successful webhook processing."""
        callback = MagicMock(return_value=[{"status": "delivered"}])
        processor = WebhookProcessor(payment_store, pi_callback=callback)

        event = self._make_event(
            "payment_intent.succeeded",
            {"id": "pi_callback_test", "amount": 999},
        )
        result = processor.process_event(event)

        assert result["status"] == "processed"
        callback.assert_called_once()
        call_args = callback.call_args
        assert call_args[0][0] == "payment_intent.succeeded"


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Webhook Signature Verification
# ═══════════════════════════════════════════════════════════════════════════════


class TestWebhookSignatureE2E:
    """Test Stripe webhook signature verification end-to-end."""

    def _sign_payload(self, payload: bytes, secret: str) -> str:
        """Generate a valid Stripe webhook signature header."""
        timestamp = str(int(time.time()))
        signed_payload = f"{timestamp}.".encode() + payload
        sig = hmac.new(
            secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()
        return f"t={timestamp},v1={sig}"

    def test_valid_signature_passes(self):
        secret = "whsec_test_secret_key_12345"
        payload = json.dumps({
            "id": "evt_sig_test",
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_sig"}},
        }).encode("utf-8")

        sig_header = self._sign_payload(payload, secret)
        event = StripeClient.verify_webhook_signature(
            payload, sig_header, secret
        )

        assert event["id"] == "evt_sig_test"
        assert event["type"] == "payment_intent.succeeded"

    def test_invalid_signature_raises(self):
        secret = "whsec_correct_secret"
        payload = b'{"id": "evt_bad_sig"}'
        # Use a current timestamp so we don't hit the tolerance check first
        ts = str(int(time.time()))
        bad_sig = f"t={ts},v1=bad_signature_value"

        with pytest.raises(ValueError, match="signature verification failed"):
            StripeClient.verify_webhook_signature(payload, bad_sig, secret)

    def test_expired_timestamp_raises(self):
        secret = "whsec_test_expired"
        payload = b'{"id": "evt_expired"}'
        old_ts = str(int(time.time()) - 600)  # 10 minutes ago
        signed = f"{old_ts}.".encode() + payload
        sig = hmac.new(
            secret.encode(), signed, hashlib.sha256
        ).hexdigest()
        sig_header = f"t={old_ts},v1={sig}"

        with pytest.raises(ValueError, match="timestamp too old"):
            StripeClient.verify_webhook_signature(
                payload, sig_header, secret, tolerance=300
            )

    def test_malformed_header_raises(self):
        with pytest.raises(ValueError):
            StripeClient.verify_webhook_signature(
                b'{}', "malformed_header", "secret"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Partnership Payment Manager (mocked Stripe API)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPartnershipPaymentManagerE2E:
    """Test the full manager with mocked Stripe API calls."""

    def test_create_partnership_payment_flow(self, tmp_path):
        """Full flow: create payment intent → record locally → verify."""
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock"}):
            mgr = PartnershipPaymentManager(db_path=tmp_path / "pay.db")

        # Mock the Stripe API response
        mgr.client._request = MagicMock(return_value={
            "id": "pi_e2e_001",
            "client_secret": "pi_e2e_001_secret_abc",
            "status": "requires_payment_method",
        })

        result = mgr.create_partnership_payment(
            partner="E2E TestCo",
            amount_cents=1000_00,
            currency="usd",
            description="Annual partnership fee",
        )

        assert result["payment_intent_id"] == "pi_e2e_001"
        assert result["client_secret"] == "pi_e2e_001_secret_abc"
        assert result["amount"] == 100000

        # Verify local record was created
        payment = mgr.store.get_payment("pi_e2e_001")
        assert payment is not None
        assert payment["partner"] == "E2E TestCo"
        assert payment["amount_cents"] == 100000
        assert payment["description"] == "Annual partnership fee"

        mgr.close()

    def test_create_partner_subscription_flow(self, tmp_path):
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock"}):
            mgr = PartnershipPaymentManager(db_path=tmp_path / "sub.db")

        # Mock customer creation
        mgr.client._request = MagicMock(side_effect=[
            {"id": "cus_e2e_001", "name": "SubTestCo"},  # create_customer
            {  # create_subscription
                "id": "sub_e2e_001",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_monthly"}}]},
            },
        ])

        result = mgr.create_partner_subscription(
            partner="SubTestCo",
            price_id="price_monthly",
            email="billing@subtestco.com",
        )

        assert result["subscription_id"] == "sub_e2e_001"
        assert result["customer_id"] == "cus_e2e_001"
        assert result["status"] == "active"

        # Verify local record
        sub = mgr.store.get_subscription("sub_e2e_001")
        assert sub is not None
        assert sub["partner"] == "SubTestCo"

        mgr.close()

    def test_refund_flow(self, tmp_path):
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock"}):
            mgr = PartnershipPaymentManager(db_path=tmp_path / "refund.db")

        # First create a payment
        mgr.store.record_payment(
            stripe_payment_id="pi_refund_001",
            partner="RefundCo",
            amount_cents=500_00,
            status="succeeded",
        )

        # Mock refund API call
        mgr.client._request = MagicMock(return_value={
            "id": "re_001",
            "status": "succeeded",
            "amount": 50000,
        })

        result = mgr.refund_payment("pi_refund_001")

        assert result["refund_id"] == "re_001"
        assert result["amount"] == 50000

        # Verify local status updated
        payment = mgr.store.get_payment("pi_refund_001")
        assert payment["status"] == "refunded"

        mgr.close()

    def test_sync_payment_status(self, tmp_path):
        with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test_mock"}):
            mgr = PartnershipPaymentManager(db_path=tmp_path / "sync.db")

        mgr.store.record_payment(
            stripe_payment_id="pi_sync_001",
            partner="SyncCo",
            amount_cents=200_00,
            status="requires_payment_method",
        )

        # Mock Stripe showing it succeeded
        mgr.client._request = MagicMock(return_value={
            "id": "pi_sync_001",
            "status": "succeeded",
        })

        result = mgr.sync_payment_status("pi_sync_001")
        assert result["status"] == "succeeded"

        payment = mgr.store.get_payment("pi_sync_001")
        assert payment["status"] == "succeeded"

        mgr.close()


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Pi Router
# ═══════════════════════════════════════════════════════════════════════════════


class TestPiEndpointStoreE2E:
    def test_register_and_list(self, pi_store):
        pi_store.register_pi("pi-01", "http://192.168.1.100:8080")
        pi_store.register_pi("pi-02", "http://192.168.1.101:8080")

        pis = pi_store.list_pis()
        assert len(pis) == 2
        ids = [p["pi_id"] for p in pis]
        assert "pi-01" in ids
        assert "pi-02" in ids

    def test_register_updates_existing(self, pi_store):
        pi_store.register_pi("pi-01", "http://old-url:8080")
        pi_store.register_pi("pi-01", "http://new-url:9090")

        pis = pi_store.list_pis()
        assert len(pis) == 1
        assert pis[0]["endpoint_url"] == "http://new-url:9090"

    def test_remove_pi(self, pi_store):
        pi_store.register_pi("pi-rm", "http://remove-me:8080")
        assert pi_store.remove_pi("pi-rm") is True
        assert pi_store.get_pi("pi-rm") is None

    def test_event_filter_matching(self, pi_store):
        pi_store.register_pi(
            "pi-payments", "http://pi-pay:8080",
            event_filter="payment_intent.succeeded,payment_intent.payment_failed",
        )
        pi_store.register_pi(
            "pi-all", "http://pi-all:8080", event_filter="*",
        )

        # Both should match payment events
        matched = pi_store.get_endpoints_for_event("payment_intent.succeeded")
        assert len(matched) == 2

        # Only pi-all should match subscription events
        matched = pi_store.get_endpoints_for_event("customer.subscription.created")
        assert len(matched) == 1
        assert matched[0]["pi_id"] == "pi-all"

    def test_route_logging(self, pi_store):
        pi_store.log_route(
            "pi-01", "payment_intent.succeeded", "abc123",
            200, 45, True,
        )
        pi_store.log_route(
            "pi-01", "payment_intent.payment_failed", "def456",
            0, 5000, False, "Connection refused",
        )

        logs = pi_store.get_route_log()
        assert len(logs) == 2

        stats = pi_store.get_pi_stats("pi-01")
        assert stats["total"] == 2
        assert stats["successes"] == 1

    def test_enabled_filter(self, pi_store):
        pi_store.register_pi("pi-on", "http://on:8080")
        pi_store.register_pi("pi-off", "http://off:8080")
        pi_store.set_enabled("pi-off", False)

        all_pis = pi_store.list_pis()
        assert len(all_pis) == 2

        enabled = pi_store.list_pis(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0]["pi_id"] == "pi-on"


class TestPiRouterE2E:
    def test_route_event_no_endpoints(self, pi_router):
        results = pi_router.route_event("some.event", {"key": "value"})
        assert results[0]["status"] == "no_endpoints"

    @patch("pi_router._send_to_endpoint")
    def test_route_event_successful_delivery(self, mock_send, pi_router):
        mock_send.return_value = (200, 42, "")

        pi_router.store.register_pi("pi-test", "http://test:8080")

        results = pi_router.route_event(
            "payment_intent.succeeded",
            {"payment_id": "pi_001", "amount": 5000},
        )

        assert len(results) == 1
        assert results[0]["status"] == "delivered"
        assert results[0]["pi_id"] == "pi-test"
        assert results[0]["response_ms"] == 42

    @patch("pi_router._send_to_endpoint")
    def test_route_event_retry_then_succeed(self, mock_send, pi_router):
        """First attempt fails, second succeeds."""
        mock_send.side_effect = [
            (500, 100, "Internal Server Error"),
            (200, 50, ""),
        ]

        pi_router.store.register_pi("pi-retry", "http://retry:8080")

        results = pi_router.route_event(
            "payment_intent.succeeded",
            {"test": True},
            max_retries=2,
        )

        assert results[0]["status"] == "delivered"
        assert results[0]["attempt"] == 2
        assert mock_send.call_count == 2

    @patch("pi_router._send_to_endpoint")
    def test_route_event_all_retries_fail(self, mock_send, pi_router):
        mock_send.return_value = (0, 5000, "Connection refused")

        pi_router.store.register_pi("pi-dead", "http://dead:8080")

        results = pi_router.route_event(
            "payment_intent.succeeded",
            {"test": True},
            max_retries=1,
        )

        assert results[0]["status"] == "failed"
        assert results[0]["error"] == "Connection refused"

    @patch("pi_router._send_to_endpoint")
    def test_route_to_multiple_pis(self, mock_send, pi_router):
        mock_send.return_value = (200, 30, "")

        pi_router.store.register_pi("pi-01", "http://pi1:8080")
        pi_router.store.register_pi("pi-02", "http://pi2:8080")
        pi_router.store.register_pi("pi-03", "http://pi3:8080")

        results = pi_router.route_event("test.event", {"data": 1})

        assert len(results) == 3
        assert all(r["status"] == "delivered" for r in results)

    def test_configure_from_env(self, pi_router):
        env_val = "pi-01:http://192.168.1.10:8080,pi-02:http://192.168.1.11:8080"
        with patch.dict(os.environ, {"PI_ENDPOINTS": env_val}):
            count = pi_router.configure_from_env()

        assert count == 2
        pis = pi_router.store.list_pis()
        assert len(pis) == 2

    def test_configure_from_file(self, pi_router, tmp_path):
        config = {
            "endpoints": [
                {"pi_id": "pi-cfg-01", "url": "http://10.0.0.1:8080", "events": "*"},
                {
                    "pi_id": "pi-cfg-02",
                    "url": "http://10.0.0.2:8080/webhook",
                    "events": "payment_intent.succeeded",
                },
            ],
        }
        config_path = tmp_path / "pi_config.json"
        config_path.write_text(json.dumps(config))

        count = pi_router.configure_from_file(config_path)
        assert count == 2

        pi = pi_router.store.get_pi("pi-cfg-02")
        assert pi["event_filter"] == "payment_intent.succeeded"


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Full Integration — Payment → Webhook → Pi Routing
# ═══════════════════════════════════════════════════════════════════════════════


class TestFullPaymentPipelineE2E:
    """End-to-end: Create payment → webhook fires → Pi gets notified."""

    @patch("pi_router._send_to_endpoint")
    def test_payment_to_pi_full_pipeline(self, mock_send, tmp_path):
        mock_send.return_value = (200, 25, "")

        # Set up all components
        payment_store = PaymentStore(tmp_path / "pipeline_payments.db")
        pi_router = PiRouter(tmp_path / "pipeline_pi.db")
        pi_router.store.register_pi("pi-payments", "http://pi-pay:8080")

        # Create Pi callback
        def pi_callback(event_type, result):
            return pi_router.route_event(event_type, result)

        processor = WebhookProcessor(payment_store, pi_callback=pi_callback)

        # Step 1: Record initial payment (simulating API call)
        payment_store.record_payment(
            stripe_payment_id="pi_full_e2e_001",
            partner="FullPipelineCo",
            amount_cents=750_00,
            status="requires_payment_method",
            description="Full pipeline test",
        )

        # Step 2: Simulate Stripe webhook
        event = {
            "id": "evt_full_pipeline_001",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_full_e2e_001",
                    "amount": 75000,
                }
            },
        }
        result = processor.process_event(event)

        # Step 3: Verify everything
        assert result["status"] == "processed"
        assert result["action"] == "payment_confirmed"

        # Payment status updated
        payment = payment_store.get_payment("pi_full_e2e_001")
        assert payment["status"] == "succeeded"

        # Pi was notified
        mock_send.assert_called()
        call_args = mock_send.call_args
        assert call_args[0][0] == "http://pi-pay:8080"

        # Route log recorded
        logs = pi_router.store.get_route_log()
        assert len(logs) >= 1
        assert logs[0]["pi_id"] == "pi-payments"

        payment_store.close()
        pi_router.close()

    @patch("pi_router._send_to_endpoint")
    def test_subscription_to_pi_pipeline(self, mock_send, tmp_path):
        """Subscription lifecycle with Pi notifications."""
        mock_send.return_value = (200, 30, "")

        payment_store = PaymentStore(tmp_path / "sub_pipe.db")
        pi_router = PiRouter(tmp_path / "sub_pi.db")
        pi_router.store.register_pi("pi-subs", "http://pi-subs:8080")

        def pi_callback(event_type, result):
            return pi_router.route_event(event_type, result)

        processor = WebhookProcessor(payment_store, pi_callback=pi_callback)

        # Subscription created
        event1 = {
            "id": "evt_sub_created",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_pipe_001",
                    "customer": "cus_pipe_001",
                    "status": "incomplete",
                    "items": {"data": [{"price": {"id": "price_pipe"}}]},
                    "metadata": {"partner": "PipelineCo"},
                }
            },
        }
        result1 = processor.process_event(event1)
        assert result1["action"] == "subscription_created"

        # Invoice paid → activates subscription
        event2 = {
            "id": "evt_inv_paid",
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "inv_pipe_001",
                    "subscription": "sub_pipe_001",
                    "amount_paid": 5000,
                }
            },
        }
        result2 = processor.process_event(event2)
        assert result2["action"] == "invoice_paid"

        # Verify subscription is now active
        sub = payment_store.get_subscription("sub_pipe_001")
        assert sub["status"] == "active"

        # Pi was notified for both events
        assert mock_send.call_count >= 2

        payment_store.close()
        pi_router.close()


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Combined Startup Metrics + Payments
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartupMetricsWithPaymentsE2E:
    """Test that startup metrics and payment tracking work together."""

    def test_startup_with_funding_and_payment(self, tmp_path):
        """Full flow: add startup → log funding → create payment → verify."""
        metrics_mgr = StartupMetricsManager(tmp_path / "metrics.db")
        payment_store = PaymentStore(tmp_path / "payments.db")

        # Add startup
        metrics_mgr.add_startup(
            "br-test-001", "IntegrationTestCo", "seed",
            mrr=50_000, burn_rate=80_000, cash_balance=1_200_000,
            headcount=8,
        )

        # Log funding round
        metrics_mgr.add_funding_round(
            "br-test-001", "Seed", 1_500_000, "BlackRoad Ventures", 8_000_000,
        )

        # Record corresponding Stripe payment
        payment_store.record_payment(
            stripe_payment_id="pi_funding_001",
            partner="IntegrationTestCo",
            amount_cents=1_500_000_00,  # $1.5M
            status="succeeded",
            description="Seed round investment",
        )

        # Verify startup metrics
        runway = metrics_mgr.get_runway("br-test-001")
        assert runway["runway_months"] == 15.0
        assert runway["runway_status"] == "watch"

        # Verify payment
        payment = payment_store.get_payment("pi_funding_001")
        assert payment["partner"] == "IntegrationTestCo"
        assert payment["status"] == "succeeded"

        # Verify funding in report
        report = metrics_mgr.investor_report("br-test-001", fmt="json")
        data = json.loads(report)
        assert data["startup"]["id"] == "br-test-001"
        assert len(data["funding"]) == 1
        assert data["funding"][0]["amount"] == 1_500_000

        metrics_mgr.close()
        payment_store.close()


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Partnerships CLI Database
# ═══════════════════════════════════════════════════════════════════════════════


class TestPartnershipsDatabaseE2E:
    def test_partnerships_crud(self, tmp_path):
        """Test partnership database operations directly."""
        import sqlite3 as _sqlite3
        db_path = tmp_path / "partnerships.db"
        conn = _sqlite3.connect(str(db_path))
        conn.row_factory = _sqlite3.Row
        conn.execute("""CREATE TABLE IF NOT EXISTS partnerships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            partner TEXT NOT NULL, type TEXT DEFAULT 'technology',
            status TEXT DEFAULT 'exploring', contact TEXT, notes TEXT,
            value_usd REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )""")
        conn.commit()

        # Add partnerships
        conn.execute(
            "INSERT INTO partnerships (partner, type, status, value_usd) VALUES (?,?,?,?)",
            ("Stripe", "integration", "active", 50000),
        )
        conn.execute(
            "INSERT INTO partnerships (partner, type, status, value_usd) VALUES (?,?,?,?)",
            ("Cloudflare", "technology", "active", 25000),
        )
        conn.execute(
            "INSERT INTO partnerships (partner, type, status, value_usd) VALUES (?,?,?,?)",
            ("AWS", "technology", "exploring", 0),
        )
        conn.commit()

        # Query
        active = conn.execute(
            "SELECT * FROM partnerships WHERE status='active'"
        ).fetchall()
        assert len(active) == 2

        total_value = conn.execute(
            "SELECT SUM(value_usd) as total FROM partnerships WHERE status='active'"
        ).fetchone()
        assert total_value["total"] == 75000

        conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Stripe Client Parameter Flattening
# ═══════════════════════════════════════════════════════════════════════════════


class TestStripeClientHelpers:
    def test_flatten_simple_params(self):
        result = StripeClient._flatten_params({"amount": 1000, "currency": "usd"})
        assert ("amount", "1000") in result
        assert ("currency", "usd") in result

    def test_flatten_nested_params(self):
        result = StripeClient._flatten_params({
            "metadata": {"partner": "TestCo", "source": "api"},
        })
        assert ("metadata[partner]", "TestCo") in result
        assert ("metadata[source]", "api") in result

    def test_flatten_list_params(self):
        result = StripeClient._flatten_params({
            "payment_method_types": ["card", "us_bank_account"],
        })
        assert ("payment_method_types[0]", "card") in result
        assert ("payment_method_types[1]", "us_bank_account") in result

    def test_flatten_none_skipped(self):
        result = StripeClient._flatten_params({"key": "val", "empty": None})
        keys = [k for k, v in result]
        assert "empty" not in keys

    def test_stripe_client_requires_key(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("STRIPE_SECRET_KEY", None)
            with pytest.raises(ValueError, match="STRIPE_SECRET_KEY"):
                StripeClient()


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: Webhook Event Store
# ═══════════════════════════════════════════════════════════════════════════════


class TestWebhookEventStoreE2E:
    def test_record_and_check_processed(self, payment_store):
        payment_store.record_webhook_event(
            "evt_store_001", "payment_intent.succeeded", '{"id": "evt_store_001"}'
        )

        assert payment_store.is_event_processed("evt_store_001") is False

        payment_store.mark_event_processed("evt_store_001")
        assert payment_store.is_event_processed("evt_store_001") is True

    def test_duplicate_event_ignored(self, payment_store):
        payment_store.record_webhook_event(
            "evt_dup", "test.event", '{"data": 1}'
        )
        # Second insert should be ignored (INSERT OR IGNORE)
        payment_store.record_webhook_event(
            "evt_dup", "test.event", '{"data": 2}'
        )
        # Verify only one event exists (the original)
        row = payment_store.conn.execute(
            "SELECT payload FROM webhook_events WHERE stripe_event_id='evt_dup'"
        ).fetchone()
        assert row["payload"] == '{"data": 1}'


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: CLI Argument Parsing (stripe_integration)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStripeCLIParsing:
    def test_create_checkout_args(self):
        from stripe_integration import _build_parser
        parser = _build_parser()
        args = parser.parse_args([
            "create-checkout", "TestPartner", "50000",
            "--currency", "eur", "--description", "Test payment",
        ])
        assert args.partner == "TestPartner"
        assert args.amount_cents == 50000
        assert args.currency == "eur"

    def test_list_payments_args(self):
        from stripe_integration import _build_parser
        parser = _build_parser()
        args = parser.parse_args([
            "list-payments", "--partner", "SomeCo", "--status", "succeeded",
        ])
        assert args.partner == "SomeCo"
        assert args.status == "succeeded"

    def test_refund_args(self):
        from stripe_integration import _build_parser
        parser = _build_parser()
        args = parser.parse_args(["refund", "pi_12345", "--amount", "2500"])
        assert args.payment_intent_id == "pi_12345"
        assert args.amount_cents == 2500


# ═══════════════════════════════════════════════════════════════════════════════
# E2E: CLI Argument Parsing (pi_router)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPiRouterCLIParsing:
    def test_configure_args(self):
        from pi_router import _build_parser
        parser = _build_parser()
        args = parser.parse_args([
            "configure", "pi-01", "http://192.168.1.100:8080",
            "--events", "payment_intent.succeeded",
        ])
        assert args.pi_id == "pi-01"
        assert args.endpoint_url == "http://192.168.1.100:8080"
        assert args.events == "payment_intent.succeeded"

    def test_route_args(self):
        from pi_router import _build_parser
        parser = _build_parser()
        args = parser.parse_args([
            "route", "test.event", '{"key": "value"}',
        ])
        assert args.event_type == "test.event"
        assert args.payload_json == '{"key": "value"}'
