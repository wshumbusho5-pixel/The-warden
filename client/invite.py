"""
Invite-code utilities.

An invite code is base64(JSON({"url": ..., "token": ...})) prefixed with
"warden:" so it's recognizable in chat. Whoever hosts the server runs this
module's CLI to mint a code and DMs the string to a friend; the client's
first-run dialog asks the friend to paste it. After that, config lives on
disk and the dialog never appears again.

We deliberately don't sign or encrypt the code — the token itself is the
only secret, and a friend always sees it after pasting. The base64 wrapping
exists so people don't have to copy two fields and so a stray space won't
silently corrupt the URL.
"""

import argparse
import base64
import json
import os
import sys


_PREFIX = "warden:"


def encode_invite(url, token):
    """Pack (url, token) into a single shareable string."""
    payload = json.dumps({"url": url, "token": token}, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
    return _PREFIX + b64


def decode_invite(code):
    """Inverse of encode_invite. Raises ValueError on malformed input."""
    code = (code or "").strip()
    if code.startswith(_PREFIX):
        code = code[len(_PREFIX):]
    if not code:
        raise ValueError("empty invite code")
    pad = (-len(code)) % 4
    try:
        raw = base64.urlsafe_b64decode(code + ("=" * pad))
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise ValueError(f"invite code is not valid: {e}")
    url = (data.get("url") or "").strip()
    token = (data.get("token") or "").strip()
    if not url:
        raise ValueError("invite code missing 'url'")
    return url, token


def config_dir():
    """Per-user config directory. Mirrors the pin-storage location."""
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/TextKit")
    if sys.platform.startswith("win"):
        return os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "TextKit")
    return os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        "textkit",
    )


def config_path():
    return os.path.join(config_dir(), "config.json")


def load_saved_config():
    """Return (url, token) from the saved config file, or None if absent/invalid."""
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return None
    url = (data.get("url") or "").strip()
    token = (data.get("token") or "").strip()
    if not url:
        return None
    return url, token


def save_config(url, token):
    """Write the resolved config to disk so future launches skip the dialog."""
    os.makedirs(config_dir(), exist_ok=True)
    with open(config_path(), "w", encoding="utf-8") as f:
        json.dump({"url": url, "token": token}, f)


def main():
    p = argparse.ArgumentParser(description="Generate a Warden invite code")
    p.add_argument("--url", required=True, help="e.g. wss://warden.example.com")
    p.add_argument("--token", default="", help="value of WARDEN_AUTH_TOKEN on the server")
    args = p.parse_args()
    print(encode_invite(args.url, args.token))


if __name__ == "__main__":
    main()
