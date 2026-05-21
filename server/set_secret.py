"""
Securely set or replace one VAR in the server .env via a hidden prompt.

Usage:  python server/set_secret.py STRIPE_SECRET_KEY

The value is read with getpass (never echoed, never passed as an argument or
through shell history), stripped of stray whitespace/newlines, and written
straight to .env with Python — so it avoids the sed-quoting and clipboard
problems that bite a `read -s | sed` one-liner.
"""

import getpass
import os
import sys


def main():
    if len(sys.argv) != 2:
        print("usage: set_secret.py VARNAME")
        return 1
    var = sys.argv[1]
    val = getpass.getpass(f"Paste value for {var} then Enter: ").strip()
    if not val:
        print("empty value; aborted")
        return 1

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repo_root, ".env")
    lines = open(path).read().splitlines() if os.path.exists(path) else []

    out, done = [], False
    for ln in lines:
        if ln.startswith(var + "="):
            out.append(f"{var}={val}")
            done = True
        else:
            out.append(ln)
    if not done:
        out.append(f"{var}={val}")

    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    os.chmod(path, 0o600)
    print(f"OK: {var} set (prefix {val[:8]}, length {len(val)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
