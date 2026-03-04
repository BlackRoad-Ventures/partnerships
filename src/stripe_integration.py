#!/usr/bin/env python3
"""
BlackRoad Ventures — Stripe Integration
========================================
Real Stripe payment processing for partnership deals:
- Create payment intents for partnership agreements
- Manage subscription billing for recurring partnerships
- Handle Stripe webhooks for payment confirmations
- Track payment status against partnership records

Requires: STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET env vars.

Usage:
    stripe_integration create-checkout <partner> <amount_cents> [--description DESC]
    stripe_integration create-subscription <partner> <price_id>
    stripe_integration list-payments [--partner PARTNER] [--status STATUS]
    stripe_integration refund <payment_intent_id> [--amount CENTS]
    stripe_integration webhook-listen <port>
    stripe_integration sync
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# ─── Config ──────────────────────────────────────────────────────────────────

STRIPE_API_BASE = "https://api.stripe.com/v1"
DB_PATH = Path.home() / ".blackroad" / "stripe_payments.db"

PAYMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS payments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    stripe_payment_id   TEXT UNIQUE NOT NULL,
    partner             TEXT NOT NULL,
    amount_cents        INTEGER NOT NULL,
    currency            TEXT NOT NULL DEFAULT 'usd',
    status              TEXT NOT NULL DEFAULT 'pending',
    description         TEXT NOT NULL DEFAULT '',
    stripe_customer_id  TEXT,
    metadata            TEXT NOT NULL DEFAULT '{}',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    stripe_subscription_id  TEXT UNIQUE NOT NULL,
    stripe_customer_id      TEXT NOT NULL,
    partner                 TEXT NOT NULL,
    price_id                TEXT NOT NULL,
    status                  TEXT NOT NULL DEFAULT 'incomplete',
    current_period_start    TEXT,
    current_period_end      TEXT,
    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS webhook_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stripe_event_id TEXT UNIQUE NOT NULL,
    event_type      TEXT NOT NULL,
    payload         TEXT NOT NULL,
    processed       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_payments_partner ON payments (partner);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments (status);
CREATE INDEX IF NOT EXISTS idx_subs_partner ON subscriptions (partner);
CREATE INDEX IF NOT EXISTS idx_webhook_type ON webhook_events (event_type);
"""


# ─── Stripe API Client ──────────────────────────────────────────────────────


class StripeAPIError(Exception):
    """Raised when a Stripe API call fails."""

    def __init__(self, status_code: int, message: str, code: str = ""):
        self.status_code = status_code
        self.code = code
        super().__init__(f"Stripe API error {status_code}: {message} ({code})")


class StripeClient:
    """Minimal Stripe API client using only stdlib (no stripe SDK dependency).

    Uses urllib to hit Stripe's REST API directly. This keeps dependencies
    minimal for deployment on constrained environments like Raspberry Pi.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("STRIPE_SECRET_KEY", "")
        if not self.api_key:
            raise ValueError(
                "STRIPE_SECRET_KEY must be set in environment or passed directly"
            )

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Make an authenticated request to Stripe API."""
        url = f"{STRIPE_API_BASE}/{endpoint}"

        body = None
        if data:
            body = urlencode(self._flatten_params(data)).encode("utf-8")

        req = Request(url, data=body, method=method)
        req.add_header(
            "Authorization", f"Bearer {self.api_key}"
        )
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        req.add_header("Stripe-Version", "2024-12-18.acacia")

        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            error_body = json.loads(e.read().decode("utf-8"))
            err = error_body.get("error", {})
            raise StripeAPIError(
                status_code=e.code,
                message=err.get("message", str(e)),
                code=err.get("code", ""),
            )

    @staticmethod
    def _flatten_params(
        data: Dict[str, Any], prefix: str = ""
    ) -> List[tuple]:
        """Flatten nested dicts for Stripe's form-encoded API."""
        items = []
        for key, val in data.items():
            full_key = f"{prefix}[{key}]" if prefix else key
            if isinstance(val, dict):
                items.extend(
                    StripeClient._flatten_params(val, full_key)
                )
            elif isinstance(val, list):
                for i, v in enumerate(val):
                    items.append((f"{full_key}[{i}]", str(v)))
            elif val is not None:
                items.append((full_key, str(val)))
        return items

    # ── Payment Intents ──────────────────────────────────────────────────

    def create_payment_intent(
        self,
        amount_cents: int,
        currency: str = "usd",
        customer_id: Optional[str] = None,
        description: str = "",
        metadata: Optional[Dict[str, str]] = None,
    ) -> dict:
        """Create a Stripe PaymentIntent."""
        params: Dict[str, Any] = {
            "amount": amount_cents,
            "currency": currency,
            "description": description,
            "payment_method_types": {"0": "card"},
        }
        if customer_id:
            params["customer"] = customer_id
        if metadata:
            params["metadata"] = metadata
        return self._request("POST", "payment_intents", params)

    def confirm_payment_intent(self, payment_intent_id: str) -> dict:
        return self._request(
            "POST", f"payment_intents/{payment_intent_id}/confirm"
        )

    def retrieve_payment_intent(self, payment_intent_id: str) -> dict:
        return self._request("GET", f"payment_intents/{payment_intent_id}")

    def cancel_payment_intent(self, payment_intent_id: str) -> dict:
        return self._request(
            "POST", f"payment_intents/{payment_intent_id}/cancel"
        )

    # ── Customers ────────────────────────────────────────────────────────

    def create_customer(
        self,
        name: str,
        email: str = "",
        metadata: Optional[Dict[str, str]] = None,
    ) -> dict:
        params: Dict[str, Any] = {"name": name}
        if email:
            params["email"] = email
        if metadata:
            params["metadata"] = metadata
        return self._request("POST", "customers", params)

    def retrieve_customer(self, customer_id: str) -> dict:
        return self._request("GET", f"customers/{customer_id}")

    # ── Subscriptions ────────────────────────────────────────────────────

    def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> dict:
        params: Dict[str, Any] = {
            "customer": customer_id,
            "items": {"0": {"price": price_id}},
        }
        if metadata:
            params["metadata"] = metadata
        return self._request("POST", "subscriptions", params)

    def cancel_subscription(self, subscription_id: str) -> dict:
        return self._request(
            "DELETE", f"subscriptions/{subscription_id}"
        )

    def retrieve_subscription(self, subscription_id: str) -> dict:
        return self._request("GET", f"subscriptions/{subscription_id}")

    # ── Refunds ──────────────────────────────────────────────────────────

    def create_refund(
        self,
        payment_intent_id: str,
        amount_cents: Optional[int] = None,
    ) -> dict:
        params: Dict[str, Any] = {"payment_intent": payment_intent_id}
        if amount_cents is not None:
            params["amount"] = amount_cents
        return self._request("POST", "refunds", params)

    # ── Webhook verification ─────────────────────────────────────────────

    @staticmethod
    def verify_webhook_signature(
        payload: bytes,
        sig_header: str,
        webhook_secret: str,
        tolerance: int = 300,
    ) -> dict:
        """Verify Stripe webhook signature and return parsed event.

        Implements Stripe's signature verification protocol:
        1. Extract timestamp and signatures from Stripe-Signature header
        2. Compute expected signature using HMAC-SHA256
        3. Compare and verify within tolerance window
        """
        elements = dict(
            item.split("=", 1)
            for item in sig_header.split(",")
            if "=" in item
        )

        timestamp = elements.get("t")
        signature = elements.get("v1")

        if not timestamp or not signature:
            raise ValueError("Invalid Stripe-Signature header format")

        ts = int(timestamp)
        if abs(time.time() - ts) > tolerance:
            raise ValueError(
                f"Webhook timestamp too old (tolerance={tolerance}s)"
            )

        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(
            webhook_secret.encode("utf-8"),
            signed_payload,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            raise ValueError("Webhook signature verification failed")

        return json.loads(payload.decode("utf-8"))


# ─── Payment Store ───────────────────────────────────────────────────────────


class PaymentStore:
    """SQLite persistence for payment records and webhook events."""

    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(PAYMENT_SCHEMA)
        self.conn.commit()

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    # ── Payments ─────────────────────────────────────────────────────────

    def record_payment(
        self,
        stripe_payment_id: str,
        partner: str,
        amount_cents: int,
        currency: str = "usd",
        status: str = "pending",
        description: str = "",
        stripe_customer_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> int:
        now = self._now()
        cur = self.conn.execute(
            """INSERT OR REPLACE INTO payments
               (stripe_payment_id, partner, amount_cents, currency, status,
                description, stripe_customer_id, metadata, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                stripe_payment_id, partner, amount_cents, currency, status,
                description, stripe_customer_id,
                json.dumps(metadata or {}), now, now,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_payment_status(
        self, stripe_payment_id: str, status: str
    ) -> bool:
        now = self._now()
        cur = self.conn.execute(
            "UPDATE payments SET status=?, updated_at=? WHERE stripe_payment_id=?",
            (status, now, stripe_payment_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_payment(self, stripe_payment_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM payments WHERE stripe_payment_id=?",
            (stripe_payment_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_payments(
        self,
        partner: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        query = "SELECT * FROM payments WHERE 1=1"
        params: list = []
        if partner:
            query += " AND partner=?"
            params.append(partner)
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    # ── Subscriptions ────────────────────────────────────────────────────

    def record_subscription(
        self,
        stripe_subscription_id: str,
        stripe_customer_id: str,
        partner: str,
        price_id: str,
        status: str = "incomplete",
    ) -> int:
        now = self._now()
        cur = self.conn.execute(
            """INSERT OR REPLACE INTO subscriptions
               (stripe_subscription_id, stripe_customer_id, partner,
                price_id, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                stripe_subscription_id, stripe_customer_id,
                partner, price_id, status, now, now,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_subscription_status(
        self, stripe_subscription_id: str, status: str
    ) -> bool:
        now = self._now()
        cur = self.conn.execute(
            "UPDATE subscriptions SET status=?, updated_at=? WHERE stripe_subscription_id=?",
            (status, now, stripe_subscription_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_subscription(self, stripe_subscription_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM subscriptions WHERE stripe_subscription_id=?",
            (stripe_subscription_id,),
        ).fetchone()
        return dict(row) if row else None

    def list_subscriptions(
        self, partner: Optional[str] = None, limit: int = 50
    ) -> List[dict]:
        if partner:
            rows = self.conn.execute(
                "SELECT * FROM subscriptions WHERE partner=? ORDER BY created_at DESC LIMIT ?",
                (partner, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM subscriptions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Webhooks ─────────────────────────────────────────────────────────

    def record_webhook_event(
        self, stripe_event_id: str, event_type: str, payload: str
    ) -> int:
        now = self._now()
        cur = self.conn.execute(
            """INSERT OR IGNORE INTO webhook_events
               (stripe_event_id, event_type, payload, created_at)
               VALUES (?, ?, ?, ?)""",
            (stripe_event_id, event_type, payload, now),
        )
        self.conn.commit()
        return cur.lastrowid

    def mark_event_processed(self, stripe_event_id: str) -> bool:
        cur = self.conn.execute(
            "UPDATE webhook_events SET processed=1 WHERE stripe_event_id=?",
            (stripe_event_id,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def is_event_processed(self, stripe_event_id: str) -> bool:
        row = self.conn.execute(
            "SELECT processed FROM webhook_events WHERE stripe_event_id=?",
            (stripe_event_id,),
        ).fetchone()
        return bool(row and row["processed"])

    def close(self) -> None:
        self.conn.close()


# ─── Webhook Handler ─────────────────────────────────────────────────────────


class WebhookProcessor:
    """Process incoming Stripe webhook events."""

    def __init__(
        self,
        store: PaymentStore,
        pi_callback=None,
    ):
        self.store = store
        self.pi_callback = pi_callback  # optional callback to route to Pi

    def process_event(self, event: dict) -> dict:
        """Route a Stripe event to the appropriate handler.

        Returns a dict with processing result.
        """
        event_id = event.get("id", "")
        event_type = event.get("type", "")
        data_obj = event.get("data", {}).get("object", {})

        # Idempotency: skip already-processed events
        if self.store.is_event_processed(event_id):
            return {"status": "skipped", "reason": "already_processed"}

        # Record the raw event
        self.store.record_webhook_event(
            event_id, event_type, json.dumps(event)
        )

        result = {"status": "processed", "event_type": event_type}

        handlers = {
            "payment_intent.succeeded": self._handle_payment_succeeded,
            "payment_intent.payment_failed": self._handle_payment_failed,
            "payment_intent.canceled": self._handle_payment_canceled,
            "customer.subscription.created": self._handle_sub_created,
            "customer.subscription.updated": self._handle_sub_updated,
            "customer.subscription.deleted": self._handle_sub_deleted,
            "invoice.paid": self._handle_invoice_paid,
            "invoice.payment_failed": self._handle_invoice_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            handler_result = handler(data_obj)
            result.update(handler_result)
        else:
            result["status"] = "ignored"
            result["reason"] = f"unhandled event type: {event_type}"

        self.store.mark_event_processed(event_id)

        # Route to Pi if callback is configured
        if self.pi_callback and result["status"] == "processed":
            try:
                self.pi_callback(event_type, result)
            except Exception:
                result["pi_routing"] = "failed"

        return result

    def _handle_payment_succeeded(self, obj: dict) -> dict:
        pi_id = obj.get("id", "")
        self.store.update_payment_status(pi_id, "succeeded")
        return {
            "payment_id": pi_id,
            "amount": obj.get("amount", 0),
            "action": "payment_confirmed",
        }

    def _handle_payment_failed(self, obj: dict) -> dict:
        pi_id = obj.get("id", "")
        self.store.update_payment_status(pi_id, "failed")
        return {
            "payment_id": pi_id,
            "action": "payment_failed",
            "failure_message": obj.get("last_payment_error", {}).get(
                "message", "unknown"
            ),
        }

    def _handle_payment_canceled(self, obj: dict) -> dict:
        pi_id = obj.get("id", "")
        self.store.update_payment_status(pi_id, "canceled")
        return {"payment_id": pi_id, "action": "payment_canceled"}

    def _handle_sub_created(self, obj: dict) -> dict:
        sub_id = obj.get("id", "")
        customer_id = obj.get("customer", "")
        status = obj.get("status", "incomplete")
        items = obj.get("items", {}).get("data", [])
        price_id = items[0]["price"]["id"] if items else ""
        partner = obj.get("metadata", {}).get("partner", "unknown")
        self.store.record_subscription(
            sub_id, customer_id, partner, price_id, status
        )
        return {"subscription_id": sub_id, "action": "subscription_created"}

    def _handle_sub_updated(self, obj: dict) -> dict:
        sub_id = obj.get("id", "")
        status = obj.get("status", "")
        self.store.update_subscription_status(sub_id, status)
        return {
            "subscription_id": sub_id,
            "action": "subscription_updated",
            "new_status": status,
        }

    def _handle_sub_deleted(self, obj: dict) -> dict:
        sub_id = obj.get("id", "")
        self.store.update_subscription_status(sub_id, "canceled")
        return {"subscription_id": sub_id, "action": "subscription_canceled"}

    def _handle_invoice_paid(self, obj: dict) -> dict:
        sub_id = obj.get("subscription", "")
        if sub_id:
            self.store.update_subscription_status(sub_id, "active")
        return {
            "invoice_id": obj.get("id", ""),
            "subscription_id": sub_id,
            "action": "invoice_paid",
            "amount": obj.get("amount_paid", 0),
        }

    def _handle_invoice_failed(self, obj: dict) -> dict:
        sub_id = obj.get("subscription", "")
        if sub_id:
            self.store.update_subscription_status(sub_id, "past_due")
        return {
            "invoice_id": obj.get("id", ""),
            "subscription_id": sub_id,
            "action": "invoice_payment_failed",
        }


# ─── Webhook HTTP Server ────────────────────────────────────────────────────


def create_webhook_server(
    store: PaymentStore,
    webhook_secret: str,
    pi_callback=None,
    port: int = 4242,
):
    """Create an HTTP server that listens for Stripe webhooks."""
    processor = WebhookProcessor(store, pi_callback)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/webhook":
                self.send_response(404)
                self.end_headers()
                return

            content_length = int(self.headers.get("Content-Length", 0))
            payload = self.rfile.read(content_length)
            sig_header = self.headers.get("Stripe-Signature", "")

            try:
                event = StripeClient.verify_webhook_signature(
                    payload, sig_header, webhook_secret
                )
            except ValueError as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
                return

            result = processor.process_event(event)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        def log_message(self, format, *args):
            # Suppress default logging, use structured output instead
            pass

    server = HTTPServer(("0.0.0.0", port), Handler)
    return server


# ─── Partnership Payment Manager ────────────────────────────────────────────


class PartnershipPaymentManager:
    """High-level facade: ties Stripe API calls to local payment records."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        db_path: Path = DB_PATH,
    ):
        self.client = StripeClient(api_key)
        self.store = PaymentStore(db_path)

    def create_partnership_payment(
        self,
        partner: str,
        amount_cents: int,
        currency: str = "usd",
        description: str = "",
        customer_id: Optional[str] = None,
    ) -> dict:
        """Create a payment intent for a partnership deal."""
        metadata = {
            "partner": partner,
            "source": "blackroad_partnerships",
            "created_by": "stripe_integration",
        }

        pi = self.client.create_payment_intent(
            amount_cents=amount_cents,
            currency=currency,
            customer_id=customer_id,
            description=description or f"BlackRoad partnership: {partner}",
            metadata=metadata,
        )

        self.store.record_payment(
            stripe_payment_id=pi["id"],
            partner=partner,
            amount_cents=amount_cents,
            currency=currency,
            status=pi.get("status", "requires_payment_method"),
            description=description,
            stripe_customer_id=customer_id,
            metadata=metadata,
        )

        return {
            "payment_intent_id": pi["id"],
            "client_secret": pi.get("client_secret", ""),
            "status": pi.get("status", ""),
            "amount": amount_cents,
            "currency": currency,
        }

    def create_partner_subscription(
        self,
        partner: str,
        price_id: str,
        email: str = "",
    ) -> dict:
        """Create a recurring subscription for a partner."""
        # Create or retrieve customer
        customer = self.client.create_customer(
            name=partner,
            email=email,
            metadata={"partner": partner, "source": "blackroad_partnerships"},
        )

        sub = self.client.create_subscription(
            customer_id=customer["id"],
            price_id=price_id,
            metadata={"partner": partner},
        )

        self.store.record_subscription(
            stripe_subscription_id=sub["id"],
            stripe_customer_id=customer["id"],
            partner=partner,
            price_id=price_id,
            status=sub.get("status", "incomplete"),
        )

        return {
            "subscription_id": sub["id"],
            "customer_id": customer["id"],
            "status": sub.get("status", ""),
            "price_id": price_id,
        }

    def refund_payment(
        self,
        payment_intent_id: str,
        amount_cents: Optional[int] = None,
    ) -> dict:
        """Issue a full or partial refund."""
        refund = self.client.create_refund(payment_intent_id, amount_cents)
        self.store.update_payment_status(payment_intent_id, "refunded")
        return {
            "refund_id": refund["id"],
            "status": refund.get("status", ""),
            "amount": refund.get("amount", 0),
        }

    def sync_payment_status(self, stripe_payment_id: str) -> dict:
        """Sync local record with Stripe's current status."""
        pi = self.client.retrieve_payment_intent(stripe_payment_id)
        status = pi.get("status", "unknown")
        self.store.update_payment_status(stripe_payment_id, status)
        return {"payment_intent_id": stripe_payment_id, "status": status}

    def close(self) -> None:
        self.store.close()


# ─── CLI ─────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stripe_integration",
        description="BlackRoad Ventures — Stripe Payment Integration",
    )
    parser.add_argument("--db", metavar="PATH", help="Override SQLite path")
    sub = parser.add_subparsers(dest="command", required=True)

    # create-checkout
    p = sub.add_parser("create-checkout", help="Create a payment intent")
    p.add_argument("partner", help="Partner name")
    p.add_argument("amount_cents", type=int, help="Amount in cents")
    p.add_argument("--currency", default="usd")
    p.add_argument("--description", default="")
    p.add_argument("--customer-id", default=None)

    # create-subscription
    p = sub.add_parser("create-subscription", help="Create a subscription")
    p.add_argument("partner", help="Partner name")
    p.add_argument("price_id", help="Stripe price ID")
    p.add_argument("--email", default="")

    # list-payments
    p = sub.add_parser("list-payments", help="List recorded payments")
    p.add_argument("--partner", default=None)
    p.add_argument("--status", default=None)

    # refund
    p = sub.add_parser("refund", help="Refund a payment")
    p.add_argument("payment_intent_id")
    p.add_argument("--amount", type=int, default=None, dest="amount_cents")

    # webhook-listen
    p = sub.add_parser("webhook-listen", help="Start webhook listener")
    p.add_argument("--port", type=int, default=4242)

    # sync
    p = sub.add_parser("sync", help="Sync payment status from Stripe")
    p.add_argument("payment_intent_id")

    return parser


def main(argv: Optional[list] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    db_path = Path(args.db) if getattr(args, "db", None) else DB_PATH

    if args.command == "list-payments":
        store = PaymentStore(db_path)
        payments = store.list_payments(
            partner=args.partner, status=args.status
        )
        print(json.dumps(payments, indent=2, default=str))
        store.close()
        return

    if args.command == "webhook-listen":
        webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        if not webhook_secret:
            print("Error: STRIPE_WEBHOOK_SECRET must be set", file=sys.stderr)
            sys.exit(1)
        store = PaymentStore(db_path)
        server = create_webhook_server(store, webhook_secret, port=args.port)
        print(f"Listening for webhooks on port {args.port}...")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down.")
        finally:
            store.close()
        return

    # Commands that need Stripe API
    mgr = PartnershipPaymentManager(db_path=db_path)
    try:
        if args.command == "create-checkout":
            result = mgr.create_partnership_payment(
                partner=args.partner,
                amount_cents=args.amount_cents,
                currency=args.currency,
                description=args.description,
                customer_id=args.customer_id,
            )
            print(json.dumps(result, indent=2))

        elif args.command == "create-subscription":
            result = mgr.create_partner_subscription(
                partner=args.partner,
                price_id=args.price_id,
                email=args.email,
            )
            print(json.dumps(result, indent=2))

        elif args.command == "refund":
            result = mgr.refund_payment(
                args.payment_intent_id, args.amount_cents
            )
            print(json.dumps(result, indent=2))

        elif args.command == "sync":
            result = mgr.sync_payment_status(args.payment_intent_id)
            print(json.dumps(result, indent=2))

    finally:
        mgr.close()


if __name__ == "__main__":
    main()
