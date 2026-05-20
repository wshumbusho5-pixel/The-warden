"""
Admin CLI for per-user tokens. Run on the server box (same machine/DB as
main_server.py). Phase 3's Stripe webhook will call the same TokenStore
methods this wraps.

Examples:
  python server/admin.py mint --label alice --limit 1000 --url wss://warden.example.com
  python server/admin.py list
  python server/admin.py revoke <token>

The DB path matches the server: $WARDEN_DB_PATH, else server/warden.db.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from token_store import TokenStore

# Reuse the client's invite-code encoder so the format stays in one place.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "client"))
try:
    from invite import encode_invite
except Exception:
    encode_invite = None


def _store():
    db_path = os.getenv(
        "WARDEN_DB_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "warden.db"),
    )
    return TokenStore(db_path)


def cmd_mint(args):
    store = _store()
    token = store.mint(label=args.label, usage_limit=args.limit)
    print(f"token: {token}")
    print(f"label: {args.label or '(none)'}")
    print(f"monthly cap: {args.limit or 'unlimited'}")
    if args.url:
        if encode_invite is None:
            print("[WARN] could not import invite encoder; share the token + URL manually")
        else:
            print("\nSend this invite code to the friend:")
            print(encode_invite(args.url, token))


def cmd_revoke(args):
    store = _store()
    if store.revoke(args.token):
        print("revoked")
    else:
        print("no such token")
        sys.exit(1)


def cmd_list(args):
    store = _store()
    rows = store.list_all()
    if not rows:
        print("(no tokens)")
        return
    for r in rows:
        cap = r["usage_limit"] or "∞"
        tok = r["token"]
        short = tok[:10] + "…" + tok[-4:]
        print(
            f"{short}  label={r['label'] or '-':<16} "
            f"status={r['status']:<8} sub={r['subscription_status']:<9} "
            f"usage={r['usage_count']}/{cap} ({r['period']})"
        )


def main():
    p = argparse.ArgumentParser(description="Warden token admin")
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("mint", help="create a new per-user token")
    m.add_argument("--label", default="", help="friend's name/email (for your reference)")
    m.add_argument("--limit", type=int, default=0, help="max requests/month (0 = unlimited)")
    m.add_argument("--url", default="", help="server URL to bake into a printable invite code")
    m.set_defaults(func=cmd_mint)

    r = sub.add_parser("revoke", help="revoke a token")
    r.add_argument("token")
    r.set_defaults(func=cmd_revoke)

    ls = sub.add_parser("list", help="list all tokens")
    ls.set_defaults(func=cmd_list)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
