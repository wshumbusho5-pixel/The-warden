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


def _g(obj, key, default=None):
    """Safe field read for Stripe objects. Their `.get` isn't dict.get
    (attribute access is intercepted), but subscripting works and raises
    KeyError for missing keys — so we catch that."""
    try:
        val = obj[key]
    except (KeyError, TypeError):
        return default
    return default if val is None else val


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


_LANDING_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Warden — Your personal AI study & research assistant</title>
<style>
  :root { color-scheme: dark; }
  body { background:#1e1e1e; color:#e8e8e8; margin:0;
         font-family:-apple-system,Segoe UI,Arial,sans-serif; line-height:1.6; }
  .wrap { max-width:720px; margin:0 auto; padding:48px 24px 72px; }
  header { display:flex; align-items:center; justify-content:space-between; margin-bottom:40px; }
  .brand { font-size:20px; font-weight:700; }
  h1 { font-size:34px; line-height:1.2; margin:0 0 14px; }
  h2 { font-size:20px; margin:36px 0 10px; }
  p { color:#bdbdbd; }
  .sub { color:#9a9a9a; font-size:17px; }
  .price { font-size:40px; font-weight:700; margin:6px 0 2px; }
  .price small { font-size:16px; color:#9a9a9a; font-weight:400; }
  ul { color:#bdbdbd; padding-left:20px; }
  li { margin:6px 0; }
  .btn { display:inline-block; background:#0a84ff; color:#fff; border:0; border-radius:10px;
         padding:15px 34px; font-size:17px; font-weight:600; cursor:pointer; margin-top:18px; }
  .card { background:#262626; border:1px solid #333; border-radius:12px; padding:24px; margin-top:18px; }
  hr { border:0; border-top:1px solid #333; margin:40px 0; }
  a { color:#5aa9ff; }
  footer { color:#7a7a7a; font-size:13px; margin-top:48px; }
</style></head>
<body><div class="wrap">
  <header><div class="brand">The Warden</div></header>

  <h1>Your personal AI study &amp; research assistant</h1>
  <p class="sub">The Warden lives in a small overlay on your desktop. Press a shortcut and it reads
  whatever's on your screen — a problem set, a document, a webpage — and helps you understand it,
  summarize it, or work through it. It remembers context as you move between tabs, so the
  conversation stays continuous with what you're looking at.</p>

  <div class="card">
    <div class="price">$100 <small>/ month</small></div>
    <p style="margin:4px 0 0">Billed monthly. Cancel anytime.</p>
    <form action="/create-checkout-session" method="POST">
      <button class="btn" type="submit">Subscribe</button>
    </form>
  </div>

  <h2>What's included</h2>
  <ul>
    <li>Desktop assistant for macOS and Windows</li>
    <li>Screen-aware answers — explanations, summaries, step-by-step help</li>
    <li>Continuous context across your tabs and apps</li>
    <li>A discreet overlay that stays out of your screen recordings, so it doesn't clutter shared screens</li>
    <li>Up to 3,500 requests per month</li>
  </ul>

  <h2>How it works</h2>
  <ul>
    <li>Subscribe below and you'll instantly receive a personal access code</li>
    <li>Download the app and paste your code on first launch</li>
    <li>Press the shortcut anytime to ask about what's on your screen</li>
  </ul>

  <h2>Billing &amp; cancellation</h2>
  <p>Subscriptions are $100/month and renew automatically until cancelled. You can cancel anytime —
  your access continues through the end of the current billing period. We don't prorate partial
  months, but if something isn't working, email us and we'll make it right.</p>

  <h2>Contact</h2>
  <p>Questions or support: <a href="mailto:wshumbusho5@gmail.com">wshumbusho5@gmail.com</a><br>
  Phone: (717) 537-8893</p>

  <hr>
  <footer>
    The Warden &middot; Operated by The Warden &middot;
    Contact: wshumbusho5@gmail.com<br>
    We only store your access token and subscription status. Your screen content is processed to
    answer your request and is not sold or shared.
  </footer>
</div></body></html>"""


@app.get("/join")
def join():
    return Response(_LANDING_HTML, mimetype="text/html")


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
    if _g(session, "payment_status") != "paid":
        return _page("Processing", "<h1>Processing…</h1><p>Hang tight, finalizing your subscription.</p>")
    email = _g(_g(session, "customer_details") or {}, "email", "")
    token = _mint_if_missing(_g(session, "customer"), _g(session, "subscription"), email)
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
        email = _g(_g(obj, "customer_details") or {}, "email", "")
        _mint_if_missing(_g(obj, "customer"), _g(obj, "subscription"), email)

    elif etype == "customer.subscription.deleted":
        row = store.get_by_stripe_customer(_g(obj, "customer"))
        if row:
            store.set_subscription(row["token"], "canceled")

    elif etype == "invoice.payment_failed":
        row = store.get_by_stripe_customer(_g(obj, "customer"))
        if row:
            store.set_subscription(row["token"], "past_due")

    elif etype == "customer.subscription.updated":
        row = store.get_by_stripe_customer(_g(obj, "customer"))
        if row:
            status = _g(obj, "status", "")
            mapped = "active" if status in ("active", "trialing") else status
            store.set_subscription(row["token"], mapped)

    return Response("", status=200)


if __name__ == "__main__":
    from waitress import serve
    print(f"[billing] listening on 127.0.0.1:{BILLING_PORT}")
    serve(app, host="127.0.0.1", port=BILLING_PORT)
