"""
Per-user access tokens backed by SQLite.

Each friend gets their own token (not a shared secret), so access can be
granted and revoked individually and metered against a monthly usage cap.
The subscription_status field is the hook for Stripe (Phase 3): a webhook
flips it to 'active'/'canceled'/'past_due' and validate() honors it.

Concurrency: one short-lived connection per call. At friend-scale volume
that's simpler and safer than sharing a connection across asyncio/Tk threads.
WAL mode keeps reads and writes from blocking each other.
"""

import os
import secrets
import sqlite3
from datetime import datetime, timezone


# subscription_status values treated as "allowed to use the service"
_ACTIVE_SUBSCRIPTION = {"manual", "active", "trialing"}


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _current_period():
    """Calendar-month bucket for usage caps, e.g. '2026-05'."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


class TokenStore:
    def __init__(self, path):
        self.path = path
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tokens (
                    token                  TEXT PRIMARY KEY,
                    label                  TEXT NOT NULL DEFAULT '',
                    status                 TEXT NOT NULL DEFAULT 'active',
                    subscription_status    TEXT NOT NULL DEFAULT 'manual',
                    stripe_customer_id     TEXT,
                    stripe_subscription_id TEXT,
                    usage_limit            INTEGER NOT NULL DEFAULT 0,
                    usage_count            INTEGER NOT NULL DEFAULT 0,
                    period                 TEXT NOT NULL DEFAULT '',
                    created_at             TEXT NOT NULL
                )
                """
            )

    # --- write ops --------------------------------------------------------

    def mint(self, label="", usage_limit=0, subscription_status="manual",
             stripe_customer_id=None, stripe_subscription_id=None):
        """Create a new token and return the secret string.

        usage_limit: max requests per calendar month. 0 = unlimited.
        """
        token = secrets.token_urlsafe(32)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tokens (token, label, status, subscription_status,
                    stripe_customer_id, stripe_subscription_id,
                    usage_limit, usage_count, period, created_at)
                VALUES (?, ?, 'active', ?, ?, ?, ?, 0, ?, ?)
                """,
                (token, label, subscription_status, stripe_customer_id,
                 stripe_subscription_id, int(usage_limit), _current_period(),
                 _now_iso()),
            )
        return token

    def revoke(self, token):
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE tokens SET status='revoked' WHERE token=?", (token,)
            )
            return cur.rowcount > 0

    def set_subscription(self, token, subscription_status,
                         stripe_customer_id=None, stripe_subscription_id=None):
        """Phase 3 hook: update billing state from a Stripe webhook."""
        sets = ["subscription_status=?"]
        args = [subscription_status]
        if stripe_customer_id is not None:
            sets.append("stripe_customer_id=?")
            args.append(stripe_customer_id)
        if stripe_subscription_id is not None:
            sets.append("stripe_subscription_id=?")
            args.append(stripe_subscription_id)
        args.append(token)
        with self._connect() as conn:
            cur = conn.execute(
                f"UPDATE tokens SET {', '.join(sets)} WHERE token=?", args
            )
            return cur.rowcount > 0

    def record_usage(self, token, n=1):
        """Increment the monthly usage counter, resetting if the month rolled."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT period, usage_count FROM tokens WHERE token=?", (token,)
            ).fetchone()
            if row is None:
                return
            period = _current_period()
            if row["period"] != period:
                conn.execute(
                    "UPDATE tokens SET period=?, usage_count=? WHERE token=?",
                    (period, n, token),
                )
            else:
                conn.execute(
                    "UPDATE tokens SET usage_count=usage_count+? WHERE token=?",
                    (n, token),
                )

    # --- read ops ---------------------------------------------------------

    def validate(self, token):
        """Return (ok: bool, reason: str). reason is 'ok' on success."""
        if not token:
            return False, "no token"
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tokens WHERE token=?", (token,)
            ).fetchone()
        if row is None:
            return False, "unknown token"
        if row["status"] != "active":
            return False, "revoked"
        if row["subscription_status"] not in _ACTIVE_SUBSCRIPTION:
            return False, f"subscription {row['subscription_status']}"
        limit = row["usage_limit"]
        if limit and limit > 0:
            # Count only usage within the current month.
            used = row["usage_count"] if row["period"] == _current_period() else 0
            if used >= limit:
                return False, "monthly usage cap reached"
        return True, "ok"

    def has_tokens(self):
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM tokens LIMIT 1").fetchone()
        return row is not None

    def get(self, token):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tokens WHERE token=?", (token,)
            ).fetchone()
        return dict(row) if row else None

    def get_by_stripe_customer(self, customer_id):
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tokens WHERE stripe_customer_id=?", (customer_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_all(self):
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tokens ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]
