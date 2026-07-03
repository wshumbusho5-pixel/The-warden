#!/usr/bin/env python3
"""
Invisible AI Assistant - Enhanced Client Agent
Full featured agent with screen capture, OCR, keyboard shortcuts, and overlay display
"""

import asyncio
import ssl
import websockets
import json
import pyperclip
from datetime import datetime
import os
import sys
import yaml
from dotenv import load_dotenv

# CA bundle path. certifi ships a trusted root cert set; using it directly
# means the PyInstaller-bundled Mac/Windows app doesn't depend on the OS
# environment setting SSL_CERT_FILE — which it doesn't on a fresh macOS,
# producing CERTIFICATE_VERIFY_FAILED on every wss:// connect.
try:
    import certifi
    _CA_BUNDLE = certifi.where()
except Exception:
    _CA_BUNDLE = None


def _build_ssl_context():
    """SSL context for wss:// using certifi when available, system roots
    otherwise. Best-effort — never blocks the connect path."""
    try:
        if _CA_BUNDLE:
            return ssl.create_default_context(cafile=_CA_BUNDLE)
        return ssl.create_default_context()
    except Exception as e:
        print(f"[ssl] context build failed: {e}; falling back to default")
        return None

# Import our modules
from screen_capture import ScreenCapture
from keyboard_listener import KeyboardListener
from overlay_display import ResponseOverlay
from history_store import HistoryStore


def _load_keyboard_config():
    """Returns (hotkey_question, hotkey_capture, hotkey_voice) tuple.
    Falls back to sensible defaults if the config file can't be read."""
    candidates = [os.path.join(os.path.dirname(__file__), 'config.yaml')]
    if hasattr(sys, '_MEIPASS'):
        candidates.append(os.path.join(sys._MEIPASS, 'client', 'config.yaml'))
    for path in candidates:
        try:
            with open(path) as f:
                cfg = yaml.safe_load(f) or {}
            kb = cfg.get('keyboard', {}) or {}
            return (
                kb.get('hotkey_question', 'ctrl+alt+w'),
                kb.get('hotkey_capture', kb.get('hotkey', 'ctrl+alt+a')),
                kb.get('hotkey_voice', 'ctrl+alt+v'),
            )
        except Exception:
            continue
    return ('ctrl+alt+w', 'ctrl+alt+a', 'ctrl+alt+v')


def _load_hotkey(default='ctrl+alt+a'):
    """Legacy single-hotkey getter. Returns the capture hotkey."""
    return _load_keyboard_config()[1]


def _ensure_server_running(host='127.0.0.1', port=8765, wait_seconds=12):
    """If the server isn't already listening on `port`, start it inside this
    same process on a daemon thread. Avoids subprocessing — when the client
    is bundled with PyInstaller, sys.executable points to the bundled
    binary, not Python, so subprocess.Popen([sys.executable, ...]) doesn't
    work the way it would for a normal script."""
    import socket
    import threading
    import time

    def is_open():
        # Use connect_ex so we don't compete with the server's own bind on
        # the same port. (Bind-probing creates a race that can prevent the
        # server from binding at all.)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            return s.connect_ex((host, port)) == 0

    if is_open():
        return None

    if hasattr(sys, '_MEIPASS'):
        server_dir = os.path.join(sys._MEIPASS, 'server')
    else:
        server_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'server',
        )
    if not os.path.isdir(server_dir):
        print(f"[WARN] server dir not found at {server_dir}; skipping auto-start")
        return None

    sys.path.insert(0, server_dir)
    os.environ['WARDEN_NO_DISPLAY'] = '1'

    def _run_server():
        try:
            from main_server import InvisibleAIServer
            server = InvisibleAIServer(enable_server_display=False)
            asyncio.run(server.start_server(host=host, port=port))
        except Exception as e:
            print(f"[ERROR] embedded server crashed: {e}")

    t = threading.Thread(target=_run_server, daemon=True)
    t.start()

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if is_open():
            return t
        time.sleep(0.4)
    print("[WARN] embedded server did not become reachable in time")
    return t


# Load environment variables. In a PyInstaller bundle the cwd isn't the
# project root, so we have to point dotenv at the bundled .env explicitly.
if hasattr(sys, '_MEIPASS'):
    load_dotenv(os.path.join(sys._MEIPASS, '.env'))
else:
    load_dotenv()


def _prompt_for_invite_code():
    """Modal first-run dialog asking for an invite code.

    Returns the entered string, or None if the user dismissed without pasting.
    Lives in its own Tk root that we destroy before the main app starts —
    the agent will spin up its own root afterwards.
    """
    import tkinter as tk

    state = {'code': None}
    win = tk.Tk()
    win.title("Welcome to TextKit")
    win.geometry("540x270")
    win.resizable(False, False)
    win.configure(bg='#1e1e1e')

    tk.Label(
        win, text="Paste your invite code",
        font=('Arial', 14, 'bold'),
        bg='#1e1e1e', fg='#ffffff',
    ).pack(pady=(24, 6))
    tk.Label(
        win,
        text="Someone shared TextKit with you. Paste the code they sent — "
             "it starts with 'warden:'.",
        font=('Arial', 10),
        bg='#1e1e1e', fg='#888888',
        wraplength=480, justify='center',
    ).pack(pady=(0, 12))

    entry = tk.Entry(
        win, font=('Courier', 11),
        bg='#2d2d2d', fg='#ffffff', insertbackground='white',
        relief=tk.FLAT,
    )
    entry.pack(padx=24, ipady=6, fill=tk.X)
    entry.focus_set()

    error_label = tk.Label(
        win, text="", font=('Arial', 9),
        bg='#1e1e1e', fg='#ff6b6b',
    )
    error_label.pack(pady=(8, 0))

    def submit():
        code = entry.get().strip()
        if not code:
            error_label.configure(text="Paste your invite code, then press Continue.")
            return
        state['code'] = code
        win.destroy()

    def cancel():
        win.destroy()

    btn_frame = tk.Frame(win, bg='#1e1e1e')
    btn_frame.pack(pady=14)
    tk.Button(
        btn_frame, text="Continue", command=submit,
        bg='#0a84ff', fg='#ffffff', font=('Arial', 10, 'bold'),
        relief=tk.FLAT, padx=24, pady=8, cursor='hand2',
    ).pack(side=tk.LEFT, padx=6)
    tk.Button(
        btn_frame, text="Quit", command=cancel,
        bg='#404040', fg='#ffffff', font=('Arial', 10),
        relief=tk.FLAT, padx=20, pady=8, cursor='hand2',
    ).pack(side=tk.LEFT, padx=6)

    win.bind('<Return>', lambda e: submit())
    win.bind('<Escape>', lambda e: cancel())
    win.mainloop()

    return state['code']


def _resolve_remote_config():
    """Make sure WARDEN_SERVER_URL is populated in os.environ before the
    agent constructs. Resolution order:

      1. Already set in env (.env, shell, LaunchAgent) → leave alone.
      2. MAIN_COMPUTER_IP set → legacy LAN mode, also leave alone.
      3. Saved invite code on disk → load + populate env.
      4. Neither → show the first-run dialog, save what the user pastes.

    Returns False only if the user dismissed the dialog without pasting.
    """
    if os.getenv("WARDEN_SERVER_URL", "").strip():
        return True
    if os.getenv("MAIN_COMPUTER_IP", "").strip():
        return True

    from invite import decode_invite, load_saved_config, save_config, config_path

    saved = load_saved_config()
    if saved is not None:
        url, token = saved
        os.environ["WARDEN_SERVER_URL"] = url
        if token:
            os.environ["WARDEN_AUTH_TOKEN"] = token
        return True

    while True:
        code = _prompt_for_invite_code()
        if not code:
            return False
        try:
            url, token = decode_invite(code)
        except ValueError as e:
            print(f"[INFO] invalid invite code ({e}); prompting again")
            continue
        save_config(url, token)
        os.environ["WARDEN_SERVER_URL"] = url
        if token:
            os.environ["WARDEN_AUTH_TOKEN"] = token
        print(f"[INFO] Saved config to {config_path()}")
        return True


class InvisibleAgentPro:
    """
    Enhanced Invisible Agent with full features:
    - Screen capture + OCR
    - Keyboard shortcuts
    - Transparent overlay
    - Background operation
    """

    def __init__(self, server_ip=None, server_port=8765):
        # WARDEN_SERVER_URL (e.g. wss://warden.example.com) takes precedence
        # so production hosts can point at a reverse proxy without caring
        # about IP/port. Fallback is the legacy ws://{ip}:{port} form.
        explicit_url = os.getenv("WARDEN_SERVER_URL", "").strip()
        if explicit_url:
            self.server_url = explicit_url
            self.server_ip = explicit_url
            self.server_port = server_port
        else:
            self.server_ip = server_ip or os.getenv("MAIN_COMPUTER_IP", "localhost")
            self.server_port = server_port
            self.server_url = f"ws://{self.server_ip}:{self.server_port}"

        self.auth_token = os.getenv("WARDEN_AUTH_TOKEN", "").strip()

        # Initialize components
        self.screen_capture = ScreenCapture()
        self.hotkey_question, self.hotkey_capture, self.hotkey_voice = _load_keyboard_config()
        self.hotkey = self.hotkey_capture  # legacy single-hotkey display

        # Voice input (local Whisper transcription). Constructed here so the
        # keyboard listener can bind the voice hotkey; if the model or
        # audio deps aren't available, VoiceInput sets enabled=False and
        # the tap becomes a no-op.
        from voice_input import VoiceInput
        self.voice_input = VoiceInput(
            on_transcript_ready=self._on_voice_transcript,
        )

        listener_bindings = {
            self.hotkey_question: self.on_focus_input,
            self.hotkey_capture: self.on_hotkey_activated,
        }
        if self.voice_input.enabled:
            listener_bindings[self.hotkey_voice] = self.on_voice_toggle

        self.keyboard_listener = KeyboardListener(
            bindings=listener_bindings,
            hotkey=self.hotkey_capture,
        )
        self.overlay = ResponseOverlay()

        # Wire the voice state indicator to the overlay so the user sees
        # "Recording…" / "Transcribing…" while a voice invocation is
        # in-flight.
        self.voice_input.on_state_change = self._on_voice_state_change

        # Local Q&A log on the user's machine. The model never sees it —
        # it's there so the user can scroll back / search past answers
        # without re-querying (zero added API cost).
        try:
            self.history_store = HistoryStore()
            print(f"[{self._timestamp()}] History store: {self.history_store.path} "
                  f"({self.history_store.count()} entries)")
        except Exception as e:
            print(f"[{self._timestamp()}] History store unavailable: {e}")
            self.history_store = None
        self.overlay.history_store = self.history_store

        # State
        self.running = False
        self.request_count = 0
        # Last N exchanges for multi-turn memory: [{role, content}, ...]
        self.history = []
        self.HISTORY_LIMIT = 5  # last 5 messages — 2-3 exchanges, lean and cheap
        # Auto-flush history if no activity for this many seconds — prevents
        # yesterday's chemistry context bleeding into today's psych session.
        self.HISTORY_IDLE_FLUSH_SECONDS = 30 * 60
        self._last_request_at = 0.0

        print(f"[{self._timestamp()}] Invisible Agent Pro initialized")
        print(f"[{self._timestamp()}] Server: {self.server_url}")

    def _timestamp(self):
        """Generate timestamp for logging"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def capture_context(self, question="", use_screen=True):
        """
        Capture comprehensive context

        Args:
            question: User's question
            use_screen: Whether to capture screen content

        Returns:
            Context dictionary
        """
        context = {
            'question': question,
            'timestamp': self._timestamp(),
            'clipboard': '',
            'screen_text': '',
            'screen_image': None,  # populated when vision mode is on
        }

        try:
            # Capture clipboard
            clipboard_content = pyperclip.paste()
            if clipboard_content:
                context['clipboard'] = clipboard_content[:1000]  # Limit size

            # Capture screen if enabled. Default path is now vision — send the
            # actual screen image so Claude can read graphs, equations,
            # diagrams, layouts, etc. OCR only sees the text; vision sees
            # everything. Falls back to OCR if image capture fails or vision
            # is explicitly disabled via WARDEN_VISION_DISABLED.
            if use_screen:
                vision_off = os.getenv('WARDEN_VISION_DISABLED', '').strip().lower() in (
                    '1', 'true', 'yes', 'on'
                )
                if not vision_off:
                    print(f"[{self._timestamp()}] Capturing screen (vision)...")
                    payload = self.screen_capture.capture_and_encode()
                    if payload:
                        context['screen_image'] = payload
                        print(f"[{self._timestamp()}] Encoded screen as JPEG "
                              f"({len(payload['data']) // 1024}KB base64)")
                if context['screen_image'] is None:
                    # Vision disabled, or capture/encode failed — fall back to OCR.
                    print(f"[{self._timestamp()}] Capturing screen (OCR fallback)...")
                    screen_text = self.screen_capture.capture_and_extract()
                    if screen_text:
                        context['screen_text'] = screen_text[:2000]
                        print(f"[{self._timestamp()}] Captured {len(screen_text)} chars from screen")

        except Exception as e:
            print(f"[{self._timestamp()}] Error capturing context: {e}")

        return context

    async def send_request(self, question="", use_screen=True):
        """
        Send request to server and get response

        Args:
            question: User's question
            use_screen: Whether to include screen capture

        Returns:
            Response dictionary
        """
        self.request_count += 1

        # Flush stale history after a period of inactivity so old topics
        # don't contaminate a fresh session.
        import time as _time
        now = _time.time()
        if (
            self.history
            and self._last_request_at
            and (now - self._last_request_at) > self.HISTORY_IDLE_FLUSH_SECONDS
        ):
            print(f"[{self._timestamp()}] Idle for >30 min — flushing conversation history")
            self.history = []
        self._last_request_at = now

        try:
            print(f"[{self._timestamp()}] Connecting to server...")

            connect_kwargs = {}
            if self.auth_token:
                connect_kwargs['additional_headers'] = {
                    'Authorization': f'Bearer {self.auth_token}',
                }
            # For wss://, pass an explicit SSL context backed by certifi
                # so verification works regardless of the OS env. Without
                # this the bundled Mac app hits CERTIFICATE_VERIFY_FAILED
                # on a fresh login session.
            if self.server_url.startswith('wss://'):
                ctx = _build_ssl_context()
                if ctx is not None:
                    connect_kwargs['ssl'] = ctx

            async with websockets.connect(self.server_url, **connect_kwargs) as websocket:
                print(f"[{self._timestamp()}] Connected!")

                # Capture context
                context = self.capture_context(question, use_screen)
                # Include the running conversation history so follow-ups have memory
                context['history'] = list(self.history)
                # Include any pinned context the user has set in the overlay
                try:
                    pinned = self.overlay.get_pin() if self.overlay else ''
                except Exception:
                    pinned = ''
                if pinned:
                    context['pinned_context'] = pinned

                # Build request
                request = {
                    'type': 'question',
                    'context': context,
                    'request_id': self.request_count
                }

                print(f"[{self._timestamp()}] Sending request #{self.request_count}...")

                # Send to server
                await websocket.send(json.dumps(request))

                # Wait for response
                print(f"[{self._timestamp()}] Waiting for AI response...")
                response = await websocket.recv()
                response_data = json.loads(response)

                print(f"[{self._timestamp()}] Response received!")

                # Update conversation memory on a successful exchange
                if response_data.get('type') == 'response':
                    answer = response_data.get('content', '')
                    if question:
                        self.history.append({'role': 'user', 'content': question})
                    if answer:
                        self.history.append({'role': 'assistant', 'content': answer})
                    # Trim to most recent N entries
                    if len(self.history) > self.HISTORY_LIMIT:
                        self.history = self.history[-self.HISTORY_LIMIT:]
                    # Append to the local Q&A log (best-effort; never block
                    # the response path on a logging failure).
                    if self.history_store is not None:
                        try:
                            model = (response_data.get('metadata') or {}).get('model', '')
                            self.history_store.add(
                                question=question or '',
                                answer=answer or '',
                                model=model,
                            )
                        except Exception as e:
                            print(f"[{self._timestamp()}] history write failed: {e}")

                return response_data

        except websockets.exceptions.ConnectionClosed as e:
            # Server actively closed the connection. 4401 is our auth-rejection
            # code — surface the close reason so the user sees something
            # meaningful (e.g. "Access paused: subscription canceled.")
            # instead of a generic "couldn't connect" message.
            print(f"[{self._timestamp()}] Server closed connection: code={e.code} reason={e.reason!r}")
            reason = (e.reason or '').strip()
            if e.code == 4401:
                content = f'Access paused: {reason}.' if reason else 'Access denied.'
            else:
                content = (
                    f'Server closed the connection (code {e.code}).'
                    + (f' {reason}' if reason else '')
                    + '\nTry again in a moment.'
                )
            return {
                'type': 'error',
                'content': content,
                'timestamp': self._timestamp(),
            }
        except websockets.exceptions.WebSocketException as e:
            # Couldn't reach the server at all (network down, TLS failed,
            # handshake rejected before close-frame, etc).
            print(f"[{self._timestamp()}] Connection error: {e}")
            return {
                'type': 'error',
                'content': f'Could not reach server at {self.server_url}.\nCheck your internet connection.',
                'timestamp': self._timestamp()
            }
        except Exception as e:
            print(f"[{self._timestamp()}] Error: {e}")
            return {
                'type': 'error',
                'content': str(e),
                'timestamp': self._timestamp()
            }

    def display_response(self, response):
        """Display AI response in overlay (respects display mode)"""
        # Check display mode
        display_mode = response.get('display_mode', 'client')

        # Only show on client if mode is 'client' or 'both'
        if display_mode not in ['client', 'both']:
            if display_mode == 'server':
                print(f"[{self._timestamp()}] Response displayed on server only")
            elif display_mode == 'silent':
                print(f"[{self._timestamp()}] Silent mode - response not displayed")
            return

        # Display normally
        if response.get('type') == 'error':
            content = f"❌ ERROR\n\n{response.get('content')}"
            metadata = None
        else:
            content = response.get('content', 'No response')
            metadata = response.get('metadata')

        # Marshal Tk calls onto the main thread (macOS requires NSWindow on main thread)
        if self.overlay.window is not None:
            self.overlay.window.after(0, lambda: self.overlay.show(content, metadata))
        else:
            self.overlay.show(content, metadata)

    def on_hotkey_activated(self):
        """Called when user presses the capture hotkey (Left+A)."""
        print(f"\n{'='*60}")
        print(f"  🔥 AI ASSISTANT ACTIVATED (capture)")
        print(f"{'='*60}\n")
        self._run_request("Help me with what's on my screen", use_screen=True)

    def on_focus_input(self):
        """Called when user presses the type-only hotkey (Left+S).
        Brings the overlay forward and focuses the input field. No screen
        capture, no recording indicator."""
        print(f"\n[{self._timestamp()}] ✏️  Focus overlay input")
        if self.overlay.window is not None:
            def _do():
                if self.overlay.is_minimized:
                    self.overlay.restore()
                self.overlay.window.lift()
                if self.overlay.input_entry is not None:
                    self.overlay.input_entry.focus_force()
            self.overlay.window.after(0, _do)

    def on_user_question(self, question):
        """Called when the user types a question into the overlay input."""
        print(f"[{self._timestamp()}] User question: {question}")
        # Run on a worker thread so Tk mainloop stays responsive
        import threading
        threading.Thread(
            target=self._run_request,
            args=(question, True),
            daemon=True,
        ).start()

    def on_voice_toggle(self):
        """Voice hotkey tap: start recording, or stop + transcribe if
        already recording."""
        if self.voice_input is None or not self.voice_input.enabled:
            return
        # Run on a worker thread so mic open / stream teardown never blocks
        # the Carbon / Win32 hotkey callback thread.
        import threading
        threading.Thread(
            target=self.voice_input.toggle,
            daemon=True,
        ).start()

    def _on_voice_transcript(self, text):
        """Whisper finished — fire a normal capture+question request with
        the transcript as the user's question."""
        text = (text or "").strip()
        if not text:
            print(f"[{self._timestamp()}] Voice: empty transcript, nothing to send")
            return
        print(f"[{self._timestamp()}] Voice: {text!r}")
        self._run_request(text, use_screen=True)

    def _on_voice_state_change(self, state):
        """State changes from VoiceInput. Show a small status label in the
        overlay so the user knows the mic / whisper is doing something.
        Uses window.after so we don't touch Tk off the main thread."""
        if self.overlay is None or self.overlay.window is None:
            return
        label = {
            "recording": "Recording…",
            "transcribing": "Transcribing…",
            "idle": "",
        }.get(state, "")
        try:
            self.overlay.window.after(
                0, lambda: self.overlay.set_status(label)
            )
        except Exception:
            pass

    def _run_request(self, question, use_screen):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            response = loop.run_until_complete(
                self.send_request(question=question, use_screen=use_screen)
            )
            self.display_response(response)
        except Exception as e:
            print(f"[{self._timestamp()}] Error handling request: {e}")
        finally:
            try:
                loop.close()
            except Exception:
                pass

    def start_background_mode(self):
        """
        Start in background mode - listens for hotkey and responds invisibly
        """
        print(f"\n{'='*60}")
        print(f"  Invisible AI Assistant - Background Mode")
        print(f"{'='*60}")
        print(f"  Server: {self.server_url}")
        print(f"  Hotkey (type):    {self.hotkey_question}  (no screen capture)")
        print(f"  Hotkey (capture): {self.hotkey_capture}  (with screen + recording indicator)")
        print(f"  Status: Running invisibly...")
        print(f"{'='*60}\n")
        print(f"[{self._timestamp()}] Press {self.hotkey_question} to type, {self.hotkey_capture} to capture")
        print(f"[{self._timestamp()}] Press Ctrl+C to stop\n")

        self.running = True

        # Pre-create overlay window on the main thread (macOS NSWindow requirement)
        self.overlay.create_window()
        self.overlay.on_submit = self.on_user_question
        # Show the overlay immediately so the user can type questions without
        # needing to fire the hotkey first. Use show() so macOS window
        # attributes (Spaces / level) are applied.
        self.overlay.window.after(
            0,
            lambda: self.overlay.show(
                "Ready. Type a question below or press the hotkey to ask about your screen.",
                None,
            ),
        )

        # Start keyboard listener (runs in its own thread)
        self.keyboard_listener.start()

        # Run Tk mainloop on the main thread so hotkey callbacks can schedule UI work
        try:
            self.overlay.window.mainloop()
        except KeyboardInterrupt:
            print(f"\n[{self._timestamp()}] Stopping...")
        finally:
            self.stop()

    def stop(self):
        """Stop the agent"""
        self.running = False
        self.keyboard_listener.stop()
        self.overlay.destroy()
        print(f"[{self._timestamp()}] Agent stopped")
        print(f"[{self._timestamp()}] Total requests: {self.request_count}")

    async def interactive_mode(self):
        """Run in interactive mode for testing"""
        print(f"\n{'='*60}")
        print(f"  Invisible AI Assistant - Interactive Mode")
        print(f"{'='*60}")
        print(f"  Server: {self.server_url}")
        print(f"  Time: {self._timestamp()}")
        print(f"{'='*60}\n")
        print("Commands:")
        print("  - Type your question for text-only mode")
        print("  - Type 'screen' to include screen capture")
        print("  - Type 'quit' to exit\n")

        while True:
            try:
                user_input = input("You: ").strip()

                if user_input.lower() in ['quit', 'exit', 'q']:
                    print(f"[{self._timestamp()}] Goodbye!")
                    break

                if not user_input:
                    continue

                # Check if user wants screen capture
                use_screen = False
                if user_input.lower() == 'screen':
                    use_screen = True
                    user_input = "Help me with what's on my screen"

                # Send request
                response = await self.send_request(user_input, use_screen)

                # Display in terminal for interactive mode
                print(f"\n{'='*60}")
                print(f"  AI Response")
                print(f"{'='*60}\n")
                print(response.get('content', 'No response'))

                metadata = response.get('metadata')
                if metadata:
                    print(f"\n{'-'*60}")
                    print(f"Model: {metadata.get('model')}")
                    print(f"Tokens: {metadata.get('tokens_used')}")
                print(f"{'='*60}\n")

            except KeyboardInterrupt:
                print(f"\n[{self._timestamp()}] Interrupted")
                break
            except Exception as e:
                print(f"[{self._timestamp()}] Error: {e}")


def _setup_file_logging():
    """Tee stdout/stderr to a per-launch log file. The bundled app is
    windowed (no console), so without this every print() vanishes and
    crashes are invisible. Best-effort — never blocks startup."""
    try:
        if sys.platform == 'darwin':
            base = os.path.expanduser('~/Library/Logs/TextKit')
        elif sys.platform.startswith('win'):
            base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'TextKit')
        else:
            base = os.path.join(os.path.expanduser('~/.local/state'), 'textkit')
        os.makedirs(base, exist_ok=True)
        log_path = os.path.join(base, 'client.log')
        logf = open(log_path, 'w', buffering=1, encoding='utf-8')

        class _Tee:
            def __init__(self, *streams):
                self._streams = [s for s in streams if s is not None]

            def write(self, data):
                for s in self._streams:
                    try:
                        s.write(data)
                    except Exception:
                        pass
                return len(data)

            def flush(self):
                for s in self._streams:
                    try:
                        s.flush()
                    except Exception:
                        pass

        sys.stdout = _Tee(sys.__stdout__, logf)
        sys.stderr = _Tee(sys.__stderr__, logf)
        print(f"[INFO] TextKit log: {log_path}")
        return log_path
    except Exception:
        return None


def main():
    """Main entry point"""
    import argparse

    _setup_file_logging()

    parser = argparse.ArgumentParser(description='Invisible AI Assistant Client')
    parser.add_argument('server_ip', nargs='?', help='Server IP address (optional)')
    parser.add_argument('--mode', choices=['background', 'interactive'],
                        default='background',
                        help='Run mode (default: background)')
    parser.add_argument('--port', type=int, default=8765,
                        help='Server port (default: 8765)')
    parser.add_argument('--reset-config', action='store_true',
                        help='Forget the saved invite code and prompt again on next launch')

    args = parser.parse_args()

    if args.reset_config:
        from invite import config_path
        try:
            os.remove(config_path())
            print(f"[INFO] Removed saved config at {config_path()}")
        except FileNotFoundError:
            pass

    # Resolve remote config (env → saved invite → first-run dialog) BEFORE
    # constructing the agent, so the existing env-var-driven code paths
    # downstream see a fully populated environment.
    if not _resolve_remote_config():
        print("[INFO] No config provided; exiting.")
        return

    # Single-instance guard: if another TextKit is already listening on the
    # port, don't start a second one — they'd fight for the keyboard hook.
    import socket as _socket
    try:
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as _s:
            _s.settimeout(0.4)
            already = _s.connect_ex(('127.0.0.1', args.port)) == 0
    except OSError:
        already = False
    if already:
        print(f"[INFO] Another TextKit is already running on port {args.port}; exiting.")
        return

    # If we're running as a bundled app or the server isn't already up,
    # spawn it ourselves so the user gets a single-launch experience.
    # Skip when pointed at a remote host — a typo there shouldn't silently
    # spin up a local fallback that pretends to be the remote server.
    remote_url = os.getenv("WARDEN_SERVER_URL", "").strip()
    is_local_target = (
        not remote_url
        and (not args.server_ip or args.server_ip in ('localhost', '127.0.0.1'))
    )
    if is_local_target:
        _ensure_server_running(port=args.port)

    # Create agent
    try:
        agent = InvisibleAgentPro(server_ip=args.server_ip, server_port=args.port)

        # Run in selected mode
        if args.mode == 'background':
            agent.start_background_mode()
        else:
            asyncio.run(agent.interactive_mode())
    except Exception:
        import traceback
        print("[FATAL] unhandled exception:")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
