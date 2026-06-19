# Warden

A desktop assistant that reads what is on your screen and answers questions
about it. The overlay window is excluded from screen-capture APIs on
macOS and Windows, so it does not appear in screen recordings,
screenshots, or screen-shares on calls.

It runs on macOS and Windows. The client is a small overlay; the AI work
happens on a hosted server that holds the Anthropic API key, meters
usage, and bills through Stripe.

## What it does

Press a hotkey, the client captures the current screen, sends the image
to Claude, and shows the response in the overlay. Two hotkeys:

- `Ctrl + Alt + A` — capture the screen and ask Claude about it.
- `Ctrl + Alt + W` — open the overlay's input box and type a question.

On macOS the modifier shows as `Option` instead of `Alt`.

The overlay sits at the top-right of whichever display the cursor is on,
stays above other windows, and is invisible to screen capture
(`NSWindowSharingNone` on macOS, `WDA_EXCLUDEFROMCAPTURE` on Windows).
A Zoom audience, a screen-recorder, and a PrintScreen all see whatever
is behind it. The user sees it on the physical display.

## Architecture

```
client/                 desktop overlay (Tk)
  main.py               agent loop, websocket client
  screen_capture.py     PIL ImageGrab + native OCR fallback
                        (Vision on macOS, Windows.Media.Ocr on Windows)
  keyboard_listener.py  Carbon hotkeys on macOS, Win32 RegisterHotKey
                        on Windows
  overlay_display.py    Tk window with invisibility flags + always-on-top
  invite.py             encodes / decodes the first-run invite code
                        (base64 of {server_url, token})

server/                 WebSocket gateway + billing
  main_server.py        websockets server, auth, request handling
  ai_providers.py       Anthropic client with retry, model fallback,
                        vision, extended thinking
  token_store.py        SQLite token store, monthly usage metering,
                        Stripe subscription state
  billing_server.py     Flask app: /join landing, Stripe Checkout,
                        webhook -> mint / revoke / pause
  admin.py              CLI for minting and revoking tokens
```

The client captures the screen, base64-encodes a JPEG, and sends it to
the server over an authenticated WSS connection. The server passes the
image to Claude as an image content block. Claude responds with text,
which the client renders in the overlay.

OCR is kept as a fallback for the case where image capture or vision is
unavailable. Set `WARDEN_VISION_DISABLED=1` on the client to force the
OCR path.

## Subscribing and installing

The intended path for a paying user:

1. Subscribe at `https://warden.areliga.com/join`. After Stripe Checkout
   completes, the success page shows an invite code that starts with
   `warden:`. Copy it.
2. Download the build for your OS from the latest release:
   `https://github.com/wshumbusho5-pixel/The-warden/releases/latest`.
   On macOS use `TextKit-macOS.zip`; on Windows use
   `TextKit-Windows.zip`.
3. Unzip the download and open the app. The app is unsigned, so the OS
   will warn the first time:
   - macOS: right-click the app, choose Open, confirm.
   - Windows: SmartScreen → More info → Run anyway.
4. Paste the invite code into the first-run dialog. The app saves it and
   does not ask again.
5. Press `Ctrl + Alt + A` (`Ctrl + Option + A` on macOS) on any screen
   to ask Claude about it.

The release bundles are produced by GitHub Actions from this repository.
The repository is public; no secrets are bundled.

## Running from source

Useful for development or to point at a different server.

Requirements: Python 3.11. On macOS, PyObjC's Cocoa, Vision, and Quartz
modules. On Windows, the `winrt` package for `Windows.Media.Ocr`.

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# macOS extras
pip install pyobjc-framework-Cocoa pyobjc-framework-Vision pyobjc-framework-Quartz
```

Run the client pointed at a server:

```bash
cd client
WARDEN_SERVER_URL=wss://warden.areliga.com \
WARDEN_AUTH_TOKEN=<token> \
python main.py
```

Run the server locally (Anthropic key required):

```bash
cd server
ANTHROPIC_API_KEY=<key> python main_server.py
```

## Configuration

Configuration is mostly through environment variables. The client also
reads `client/config.yaml` for the hotkey assignments.

### Client

- `WARDEN_SERVER_URL` — WSS URL of the server. Set automatically by the
  invite code on first run, but can be overridden.
- `WARDEN_AUTH_TOKEN` — bearer token. Set automatically by the invite
  code on first run.
- `WARDEN_VISION_DISABLED=1` — disable vision; send OCR text only.
- `WARDEN_NO_DISPLAY=1` — headless mode; used by CI smoke tests.

### Server

- `ANTHROPIC_API_KEY` — required.
- `WARDEN_AUTH_TOKEN` — master token. Always accepted, never metered.
- `WARDEN_PRIMARY_MODEL` — primary model. Default
  `claude-sonnet-4-6`; `claude-opus-4-7` is also supported.
- `WARDEN_FALLBACK_MODELS` — comma-separated chain used when the
  primary returns a transient overload. Default
  `claude-opus-4-7,claude-haiku-4-5-20251001`.
- `WARDEN_THINKING_BUDGET` — extended thinking budget. Default 4000.
  Set to 0 to disable.
- `WARDEN_SUB_USAGE_LIMIT` — per-subscriber monthly request cap.
  Default 3500.
- `WARDEN_DB_PATH` — path to the SQLite token store. Defaults to
  `server/warden.db` next to the server.
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID` —
  Stripe configuration for the billing service.
- `WARDEN_PUBLIC_URL` — public URL used for Stripe redirect targets.
- `WARDEN_WSS_URL` — WSS URL baked into invite codes minted by the
  server.

## Build and release

CI builds the desktop bundles on tag push.

```bash
git tag v0.1.x
git push origin v0.1.x
```

The workflow runs a Windows OCR smoke test, builds both `.app` and
`.exe` bundles with PyInstaller, and attaches `TextKit-macOS.zip` and
`TextKit-Windows.zip` to the GitHub release.

## License

Personal project, source-available. Commercial reuse is not licensed
without permission.
