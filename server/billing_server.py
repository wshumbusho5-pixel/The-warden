"""
Stripe self-serve subscription server for Warden.

A small Flask app run behind Caddy alongside the WebSocket server. Flow:
  /join                     landing page with a Subscribe button
  /create-checkout-session  creates a Stripe Checkout session, redirects to it
  /success                  after payment, shows the invite code to paste in TextKit
  /webhook                  Stripe events -> mint / revoke / pause the per-user token

Token lifecycle rides on the shared SQLite token store (same DB the WS server
reads). checkout.session.completed mints an active token; subscription
cancellation revokes it; a failed payment pauses it (past_due). The /success
page also mints-if-missing so the invite code shows instantly even if the
webhook is a beat behind — get_by_stripe_customer keeps it idempotent.

Config (env):
  STRIPE_SECRET_KEY       sk_test_... / sk_live_...
  STRIPE_WEBHOOK_SECRET   whsec_...
  STRIPE_PRICE_ID         price_...   ($/mo recurring price)
  WARDEN_PUBLIC_URL       https://warden.areliga.com   (redirect base)
  WARDEN_WSS_URL          wss://warden.areliga.com     (baked into invite codes)
  WARDEN_SUB_USAGE_LIMIT  per-subscriber monthly request cap (default 3500)
  BILLING_PORT            local port for waitress (default 8766)
  WARDEN_DB_PATH          shared with main_server (default server/warden.db)
"""

import os
import sys

import stripe
from dotenv import load_dotenv
from flask import Flask, request, redirect, abort, Response

# Load .env when run directly; under systemd the EnvironmentFile already
# populates these, so this is a harmless no-op there.
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from token_store import TokenStore

# Reuse the client's invite-code encoder so the format stays in one place.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "client"))
from invite import encode_invite


STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")
PUBLIC_URL = os.environ.get("WARDEN_PUBLIC_URL", "https://warden.areliga.com").rstrip("/")
WSS_URL = os.environ.get("WARDEN_WSS_URL", "wss://warden.areliga.com")
USAGE_LIMIT = int(os.environ.get("WARDEN_SUB_USAGE_LIMIT", "3500"))
BILLING_PORT = int(os.environ.get("BILLING_PORT", "8766"))
DB_PATH = os.environ.get(
    "WARDEN_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "warden.db"),
)

stripe.api_key = STRIPE_SECRET_KEY
store = TokenStore(DB_PATH)
app = Flask(__name__)


def _page(title, body):
    return Response(
        f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body {{ background:#1e1e1e; color:#eee; font-family:-apple-system,Segoe UI,Arial,sans-serif;
         display:flex; min-height:100vh; align-items:center; justify-content:center; margin:0; }}
  .card {{ max-width:560px; padding:40px; text-align:center; }}
  h1 {{ font-size:28px; margin:0 0 12px; }}
  p {{ color:#aaa; line-height:1.5; }}
  .btn {{ display:inline-block; background:#0a84ff; color:#fff; border:0; border-radius:8px;
         padding:14px 28px; font-size:16px; font-weight:600; cursor:pointer; text-decoration:none; }}
  code {{ display:block; background:#2d2d2d; color:#7CFC9B; padding:14px; border-radius:8px;
         word-break:break-all; margin:18px 0; font-size:13px; }}
  ol {{ text-align:left; color:#aaa; line-height:1.7; }}
</style></head><body><div class="card">{body}</div></body></html>""",
        mimetype="text/html",
    )


@app.get("/join")
def join():
    return _page(
        "Join The Warden",
        """<h1>The Warden</h1>
        <p>Your always-on AI that sees your screen across every tab — invisible in screen shares.
        Subscribe to get your personal access code.</p>
        <form action="/create-checkout-session" method="POST">
          <button class="btn" type="submit">Subscribe</button>
        </form>""",
    )


@app.post("/create-checkout-session")
def create_checkout_session():
    if not (STRIPE_SECRET_KEY and PRICE_ID):
        abort(503, "billing not configured")
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        success_url=f"{PUBLIC_URL}/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{PUBLIC_URL}/join",
    )
    return redirect(session.url, code=303)


def _mint_if_missing(customer_id, subscription_id=None, email=""):
    """Return the token for this Stripe customer, minting an active one if none
    exists yet. Idempotent — safe to call from both /success and the webhook."""
    if not customer_id:
        return None
    row = store.get_by_stripe_customer(customer_id)
    if row:
        return row["token"]
    token = store.mint(
        label=email or customer_id,
        usage_limit=USAGE_LIMIT,
        subscription_status="active",
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
    )
    return token


@app.get("/success")
def success():
    session_id = request.args.get("session_id", "")
    if not session_id:
        abort(400)
    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except Exception:
        abort(400)
    if session.get("payment_status") != "paid":
        return _page("Processing", "<h1>Processing…</h1><p>Hang tight, finalizing your subscription.</p>")
    email = (session.get("customer_details") or {}).get("email", "")
    token = _mint_if_missing(session.get("customer"), session.get("subscription"), email)
    if not token:
        return _page(
            "Almost there",
            '<h1>Almost there…</h1><p>Your code is being generated. '
            'Refresh this page in a few seconds.</p>'
            '<meta http-equiv="refresh" content="4">',
        )
    code = encode_invite(WSS_URL, token)
    return _page(
        "You're in",
        f"""<h1>You're in 🎉</h1>
        <p>Copy your invite code and paste it into the TextKit app on first launch:</p>
        <code>{code}</code>
        <ol>
          <li>Download &amp; open the TextKit app</li>
          <li>Paste the code above into the "Paste your invite code" box</li>
          <li>Press Ctrl+Option+A (Win: Ctrl+Alt+A) to use it</li>
        </ol>""",
    )


@app.post("/webhook")
def webhook():
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    if not WEBHOOK_SECRET:
        abort(503, "webhook secret not configured")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WEBHOOK_SECRET)
    except Exception:
        abort(400)

    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "checkout.session.completed":
        email = (obj.get("customer_details") or {}).get("email", "")
        _mint_if_missing(obj.get("customer"), obj.get("subscription"), email)

    elif etype == "customer.subscription.deleted":
        row = store.get_by_stripe_customer(obj.get("customer"))
        if row:
            store.set_subscription(row["token"], "canceled")

    elif etype == "invoice.payment_failed":
        row = store.get_by_stripe_customer(obj.get("customer"))
        if row:
            store.set_subscription(row["token"], "past_due")

    elif etype == "customer.subscription.updated":
        row = store.get_by_stripe_customer(obj.get("customer"))
        if row:
            status = obj.get("status", "")
            mapped = "active" if status in ("active", "trialing") else status
            store.set_subscription(row["token"], mapped)

    return Response("", status=200)


if __name__ == "__main__":
    from waitress import serve
    print(f"[billing] listening on 127.0.0.1:{BILLING_PORT}")
    serve(app, host="127.0.0.1", port=BILLING_PORT)
