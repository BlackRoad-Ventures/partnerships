#!/usr/bin/env python3
"""
BlackRoad Ventures — Raspberry Pi Event Router
===============================================
Routes Stripe webhook events, deployment notifications, and partnership
updates to Raspberry Pi endpoints on the local network or via tunnels.

Supports:
- Direct HTTP routing to Pi endpoints (LAN or Cloudflare Tunnel)
- Event filtering by type
- Retry with exponential backoff
- Health monitoring of Pi fleet
- SQLite event log for audit trail

Configuration via environment or config file:
    PI_ENDPOINTS=pi-01:http://192.168.1.100:8080,pi-02:http://10.0.0.50:8080
    PI_CONFIG_PATH=~/.blackroad/pi_config.json

Usage:
    pi_router configure <pi_id> <endpoint_url> [--events EVENT_TYPES]
    pi_router list
    pi_router health
    pi_router route <event_type> <payload_json>
    pi_router tail [--lines N]
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


# ─── Config ──────────────────────────────────────────────────────────────────

DB_PATH = Path.home() / ".blackroad" / "pi_router.db"
CONFIG_PATH = Path.home() / ".blackroad" / "pi_config.json"

ROUTER_SCHEMA = """
CREATE TABLE IF NOT EXISTS pi_endpoints (
    pi_id           TEXT PRIMARY KEY,
    endpoint_url    TEXT NOT NULL,
    event_filter    TEXT NOT NULL DEFAULT '*',
    enabled         INTEGER NOT NULL DEFAULT 1,
    last_seen       TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS route_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pi_id           TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    payload_hash    TEXT NOT NULL,
    status_code     INTEGER,
    response_ms     INTEGER,
    success         INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_route_log_pi ON route_log (pi_id, created_at);
CREATE INDEX IF NOT EXISTS idx_route_log_event ON route_log (event_type);
"""

# Default retry config
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds
REQUEST_TIMEOUT = 10  # seconds


# ─── Pi Endpoint Store ───────────────────────────────────────────────────────


class PiEndpointStore:
    """Manage registered Pi endpoints and routing logs."""

    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(ROUTER_SCHEMA)
        self.conn.commit()

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def register_pi(
        self,
        pi_id: str,
        endpoint_url: str,
        event_filter: str = "*",
    ) -> None:
        """Register or update a Pi endpoint."""
        now = self._now()
        self.conn.execute(
            """INSERT INTO pi_endpoints (pi_id, endpoint_url, event_filter, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(pi_id) DO UPDATE SET
                   endpoint_url=excluded.endpoint_url,
                   event_filter=excluded.event_filter,
                   updated_at=excluded.updated_at""",
            (pi_id, endpoint_url, event_filter, now, now),
        )
        self.conn.commit()

    def remove_pi(self, pi_id: str) -> bool:
        cur = self.conn.execute(
            "DELETE FROM pi_endpoints WHERE pi_id=?", (pi_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_pi(self, pi_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM pi_endpoints WHERE pi_id=?", (pi_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_pis(self, enabled_only: bool = False) -> List[dict]:
        query = "SELECT * FROM pi_endpoints"
        if enabled_only:
            query += " WHERE enabled=1"
        query += " ORDER BY pi_id"
        rows = self.conn.execute(query).fetchall()
        return [dict(r) for r in rows]

    def update_last_seen(self, pi_id: str) -> None:
        now = self._now()
        self.conn.execute(
            "UPDATE pi_endpoints SET last_seen=?, updated_at=? WHERE pi_id=?",
            (now, now, pi_id),
        )
        self.conn.commit()

    def set_enabled(self, pi_id: str, enabled: bool) -> bool:
        cur = self.conn.execute(
            "UPDATE pi_endpoints SET enabled=? WHERE pi_id=?",
            (1 if enabled else 0, pi_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def get_endpoints_for_event(self, event_type: str) -> List[dict]:
        """Return all enabled endpoints that match the given event type."""
        pis = self.list_pis(enabled_only=True)
        matched = []
        for pi in pis:
            filt = pi["event_filter"]
            if filt == "*" or event_type in filt.split(","):
                matched.append(pi)
        return matched

    # ── Route logging ────────────────────────────────────────────────────

    def log_route(
        self,
        pi_id: str,
        event_type: str,
        payload_hash: str,
        status_code: Optional[int],
        response_ms: int,
        success: bool,
        error_message: str = "",
    ) -> int:
        now = self._now()
        cur = self.conn.execute(
            """INSERT INTO route_log
               (pi_id, event_type, payload_hash, status_code,
                response_ms, success, error_message, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pi_id, event_type, payload_hash, status_code,
                response_ms, 1 if success else 0, error_message, now,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_route_log(self, limit: int = 50) -> List[dict]:
        rows = self.conn.execute(
            "SELECT * FROM route_log ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_pi_stats(self, pi_id: str) -> dict:
        """Get delivery stats for a specific Pi."""
        row = self.conn.execute(
            """SELECT
                COUNT(*) as total,
                SUM(success) as successes,
                AVG(response_ms) as avg_ms,
                MAX(created_at) as last_route
            FROM route_log WHERE pi_id=?""",
            (pi_id,),
        ).fetchone()
        return dict(row) if row else {}

    def close(self) -> None:
        self.conn.close()


# ─── HTTP Sender ─────────────────────────────────────────────────────────────


def _send_to_endpoint(
    endpoint_url: str,
    payload: dict,
    timeout: int = REQUEST_TIMEOUT,
) -> tuple:
    """Send JSON payload to an endpoint. Returns (status_code, response_ms, error)."""
    parsed = urlparse(endpoint_url)
    is_https = parsed.scheme == "https"
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if is_https else 80)
    path = parsed.path or "/"

    body = json.dumps(payload).encode("utf-8")
    start = time.monotonic()

    try:
        if is_https:
            conn = HTTPSConnection(host, port, timeout=timeout)
        else:
            conn = HTTPConnection(host, port, timeout=timeout)

        conn.request(
            "POST",
            path,
            body=body,
            headers={
                "Content-Type": "application/json",
                "X-BlackRoad-Source": "pi-router",
                "X-BlackRoad-Event": payload.get("event_type", "unknown"),
            },
        )
        resp = conn.getresponse()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        status = resp.status
        conn.close()
        return (status, elapsed_ms, "")
    except Exception as e:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return (0, elapsed_ms, str(e))


# ─── Router ──────────────────────────────────────────────────────────────────


class PiRouter:
    """Routes events to registered Raspberry Pi endpoints with retry logic."""

    def __init__(self, db_path: Path = DB_PATH):
        self.store = PiEndpointStore(db_path)

    def route_event(
        self,
        event_type: str,
        payload: dict,
        max_retries: int = MAX_RETRIES,
    ) -> List[dict]:
        """Route an event to all matching Pi endpoints.

        Returns a list of delivery results.
        """
        endpoints = self.store.get_endpoints_for_event(event_type)
        if not endpoints:
            return [{"status": "no_endpoints", "event_type": event_type}]

        # Build the envelope
        envelope = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "source": "blackroad_partnerships",
            "data": payload,
        }

        import hashlib
        payload_hash = hashlib.sha256(
            json.dumps(envelope, sort_keys=True).encode()
        ).hexdigest()[:16]

        results = []
        for ep in endpoints:
            result = self._deliver_with_retry(
                ep, envelope, payload_hash, max_retries
            )
            results.append(result)

        return results

    def _deliver_with_retry(
        self,
        endpoint: dict,
        envelope: dict,
        payload_hash: str,
        max_retries: int,
    ) -> dict:
        """Deliver to a single endpoint with exponential backoff retry."""
        pi_id = endpoint["pi_id"]
        url = endpoint["endpoint_url"]

        for attempt in range(max_retries + 1):
            status_code, response_ms, error = _send_to_endpoint(url, envelope)

            success = 200 <= status_code < 300

            if success:
                self.store.update_last_seen(pi_id)
                self.store.log_route(
                    pi_id, envelope["event_type"], payload_hash,
                    status_code, response_ms, True,
                )
                return {
                    "pi_id": pi_id,
                    "status": "delivered",
                    "status_code": status_code,
                    "response_ms": response_ms,
                    "attempt": attempt + 1,
                }

            # Last attempt — log failure
            if attempt == max_retries:
                self.store.log_route(
                    pi_id, envelope["event_type"], payload_hash,
                    status_code, response_ms, False, error,
                )
                return {
                    "pi_id": pi_id,
                    "status": "failed",
                    "status_code": status_code,
                    "response_ms": response_ms,
                    "error": error,
                    "attempts": attempt + 1,
                }

            # Exponential backoff
            delay = RETRY_BASE_DELAY * (2 ** attempt)
            time.sleep(delay)

        # Should not reach here, but just in case
        return {"pi_id": pi_id, "status": "failed", "error": "max retries exceeded"}

    def check_health(self) -> List[dict]:
        """Ping all registered Pi endpoints and return health status."""
        pis = self.store.list_pis()
        results = []
        for pi in pis:
            health_payload = {
                "event_type": "health_check",
                "timestamp": datetime.utcnow().isoformat(),
            }
            status_code, response_ms, error = _send_to_endpoint(
                pi["endpoint_url"], health_payload, timeout=5
            )
            healthy = 200 <= status_code < 300
            if healthy:
                self.store.update_last_seen(pi["pi_id"])
            stats = self.store.get_pi_stats(pi["pi_id"])
            results.append({
                "pi_id": pi["pi_id"],
                "endpoint": pi["endpoint_url"],
                "healthy": healthy,
                "status_code": status_code,
                "response_ms": response_ms,
                "error": error if not healthy else "",
                "enabled": bool(pi["enabled"]),
                "last_seen": pi.get("last_seen"),
                "total_deliveries": stats.get("total", 0),
                "success_rate": (
                    round(stats["successes"] / stats["total"] * 100, 1)
                    if stats.get("total")
                    else 0
                ),
            })
        return results

    def configure_from_env(self) -> int:
        """Load Pi endpoints from PI_ENDPOINTS env var.

        Format: pi-01:http://192.168.1.100:8080,pi-02:http://10.0.0.50:8080
        """
        env_val = os.environ.get("PI_ENDPOINTS", "")
        if not env_val:
            return 0

        count = 0
        for entry in env_val.split(","):
            entry = entry.strip()
            if ":" not in entry:
                continue
            # Split on first colon only for pi_id, rest is URL
            parts = entry.split(":", 1)
            if len(parts) != 2:
                continue
            pi_id = parts[0]
            url = parts[1]
            # Handle the case where URL starts with http
            if not url.startswith("http"):
                # pi_id:host:port format
                url = f"http://{url}"
            self.store.register_pi(pi_id, url)
            count += 1
        return count

    def configure_from_file(self, config_path: Path = CONFIG_PATH) -> int:
        """Load Pi endpoints from a JSON config file.

        Expected format:
        {
            "endpoints": [
                {"pi_id": "pi-01", "url": "http://192.168.1.100:8080", "events": "*"},
                {"pi_id": "pi-02", "url": "http://10.0.0.50:8080/webhook", "events": "payment_intent.succeeded,invoice.paid"}
            ]
        }
        """
        if not config_path.exists():
            return 0

        with open(config_path) as f:
            config = json.load(f)

        count = 0
        for ep in config.get("endpoints", []):
            self.store.register_pi(
                ep["pi_id"],
                ep["url"],
                ep.get("events", "*"),
            )
            count += 1
        return count

    def close(self) -> None:
        self.store.close()


# ─── Callback factory for Stripe webhook integration ────────────────────────


def make_pi_callback(
    db_path: Path = DB_PATH,
) -> callable:
    """Create a callback function for use with WebhookProcessor.

    Usage:
        from pi_router import make_pi_callback
        callback = make_pi_callback()
        processor = WebhookProcessor(store, pi_callback=callback)
    """
    router = PiRouter(db_path)

    def callback(event_type: str, result: dict) -> List[dict]:
        return router.route_event(event_type, result)

    return callback


# ─── CLI ─────────────────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pi_router",
        description="BlackRoad Ventures — Raspberry Pi Event Router",
    )
    parser.add_argument("--db", metavar="PATH", help="Override SQLite path")
    sub = parser.add_subparsers(dest="command", required=True)

    # configure
    p = sub.add_parser("configure", help="Register a Pi endpoint")
    p.add_argument("pi_id", help="Unique Pi identifier (e.g. pi-01)")
    p.add_argument("endpoint_url", help="HTTP endpoint URL")
    p.add_argument(
        "--events", default="*",
        help="Comma-separated event types to receive, or * for all",
    )

    # remove
    p = sub.add_parser("remove", help="Remove a Pi endpoint")
    p.add_argument("pi_id")

    # list
    sub.add_parser("list", help="List all Pi endpoints")

    # health
    sub.add_parser("health", help="Health check all Pi endpoints")

    # route
    p = sub.add_parser("route", help="Manually route an event")
    p.add_argument("event_type", help="Event type string")
    p.add_argument("payload_json", help="JSON payload string")

    # tail
    p = sub.add_parser("tail", help="Show recent route log entries")
    p.add_argument("--lines", type=int, default=20)

    # load-env
    sub.add_parser("load-env", help="Load endpoints from PI_ENDPOINTS env var")

    # load-config
    p = sub.add_parser("load-config", help="Load endpoints from config file")
    p.add_argument("--path", default=None)

    return parser


def main(argv: Optional[list] = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    db_path = Path(args.db) if getattr(args, "db", None) else DB_PATH
    router = PiRouter(db_path)

    try:
        if args.command == "configure":
            router.store.register_pi(
                args.pi_id, args.endpoint_url, args.events
            )
            print(f"Registered {args.pi_id} -> {args.endpoint_url}")
            print(f"  Events: {args.events}")

        elif args.command == "remove":
            if router.store.remove_pi(args.pi_id):
                print(f"Removed {args.pi_id}")
            else:
                print(f"Pi {args.pi_id} not found")

        elif args.command == "list":
            pis = router.store.list_pis()
            if not pis:
                print("No Pi endpoints registered.")
            else:
                print(f"{'ID':<15} {'Endpoint':<45} {'Events':<20} {'Last Seen'}")
                print("-" * 100)
                for pi in pis:
                    ls = pi.get("last_seen") or "never"
                    en = "" if pi["enabled"] else " [DISABLED]"
                    print(
                        f"{pi['pi_id']:<15} {pi['endpoint_url']:<45} "
                        f"{pi['event_filter']:<20} {ls}{en}"
                    )

        elif args.command == "health":
            results = router.check_health()
            for r in results:
                status = "OK" if r["healthy"] else "DOWN"
                print(
                    f"  [{status}] {r['pi_id']:<15} "
                    f"{r['response_ms']}ms  "
                    f"deliveries={r['total_deliveries']}  "
                    f"success={r['success_rate']}%"
                )
                if r["error"]:
                    print(f"         error: {r['error']}")

        elif args.command == "route":
            payload = json.loads(args.payload_json)
            results = router.route_event(args.event_type, payload)
            print(json.dumps(results, indent=2))

        elif args.command == "tail":
            logs = router.store.get_route_log(limit=args.lines)
            for log in logs:
                ok = "OK" if log["success"] else "FAIL"
                print(
                    f"  [{ok}] {log['created_at'][:19]} "
                    f"{log['pi_id']:<15} {log['event_type']:<35} "
                    f"{log['response_ms']}ms"
                )
                if log.get("error_message"):
                    print(f"         {log['error_message']}")

        elif args.command == "load-env":
            count = router.configure_from_env()
            print(f"Loaded {count} endpoints from PI_ENDPOINTS env var")

        elif args.command == "load-config":
            path = Path(args.path) if args.path else CONFIG_PATH
            count = router.configure_from_file(path)
            print(f"Loaded {count} endpoints from {path}")

    finally:
        router.close()


if __name__ == "__main__":
    main()
