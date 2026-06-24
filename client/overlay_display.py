"""
Transparent overlay window for displaying AI responses.

Cross-platform: macOS uses NSWindow APIs for screen-capture exclusion + Spaces
behavior. Windows uses SetWindowDisplayAffinity for the same "invisible in
screen shares" effect. Linux has no equivalent — the overlay is visible to
capture there.
"""

import sys
import tkinter as tk
from tkinter import scrolledtext
import threading


_IS_MAC = sys.platform == 'darwin'
_IS_WIN = sys.platform.startswith('win')


# ---------------------------------------------------------------------------
# Typography + palette — tuned to feel premium in a small overlay panel.
# Larger body type than the original (Claude-style), generous line spacing,
# deeper near-black background, off-white text for less harsh contrast.
# ---------------------------------------------------------------------------
if _IS_MAC:
    _UI_FAMILY = "SF Pro Text"
elif _IS_WIN:
    _UI_FAMILY = "Segoe UI Variable"
else:
    _UI_FAMILY = "Helvetica"

_BODY_FONT     = (_UI_FAMILY, 14)
_BODY_FONT_BIG = (_UI_FAMILY, 15)
_TITLE_FONT    = (_UI_FAMILY, 13, "bold")
_LABEL_FONT    = (_UI_FAMILY, 11)
_MUTED_FONT    = (_UI_FAMILY, 10)
_BTN_FONT      = (_UI_FAMILY, 11)
_BTN_FONT_BOLD = (_UI_FAMILY, 11, "bold")

_BG       = "#161616"   # window background
_PANEL    = "#1d1d1d"   # title/section background
_FIELD    = "#222222"   # text widget / input field
_FIELD_HI = "#272727"   # pinned context field
_FG       = "#ECECEC"   # body text
_FG_MUTED = "#9A9AA0"   # subtle labels
_ACCENT   = "#0a84ff"   # primary action
_BTN_BG   = "#3a3a3a"   # secondary button


def _set_accessory_activation_policy():
    """macOS-only: make the Python process an 'accessory' app — no Dock icon,
    behaves like a menu-bar utility. Accessory apps' windows can appear over
    fullscreen apps and on every Space more reliably than regular apps.
    No-op on Windows/Linux (they don't have this concept)."""
    if not _IS_MAC:
        return
    try:
        from Cocoa import NSApp
        NSApplicationActivationPolicyAccessory = 1
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception as e:
        print(f"[WARN] Could not set accessory activation policy: {e}")


def _exclude_from_screen_capture_windows(tk_window):
    """Windows: SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE) makes the
    window appear blank in screen recordings / shares while staying visible
    to the user. Needs Windows 10 2004+; falls back to WDA_MONITOR on older."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
        user32.GetParent.argtypes = [wintypes.HWND]
        user32.GetParent.restype = wintypes.HWND

        tk_window.update_idletasks()
        # Tk's winfo_id() returns the inner widget HWND; the decorated
        # top-level is its parent. SetWindowDisplayAffinity wants the top-level.
        hwnd = tk_window.winfo_id()
        parent = user32.GetParent(hwnd)
        if parent:
            hwnd = parent

        WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Windows 10 2004+
        if user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE):
            print("[INFO] Overlay configured: excluded from screen capture (WDA_EXCLUDEFROMCAPTURE)")
            return True

        WDA_MONITOR = 0x00000001  # older fallback — also blanks in captures
        if user32.SetWindowDisplayAffinity(hwnd, WDA_MONITOR):
            print("[INFO] Overlay configured: excluded from screen capture (WDA_MONITOR fallback)")
            return True

        print("[WARN] SetWindowDisplayAffinity failed; overlay visible to screen capture")
        return False
    except Exception as e:
        print(f"[WARN] Windows screen-capture exclusion not available: {e}")
        return False


def _exclude_from_screen_capture(tk_window):
    """Hide the overlay from screen capture using the platform's native API.
    Returns truthy on success. On Linux there's no portable equivalent."""
    if _IS_WIN:
        return _exclude_from_screen_capture_windows(tk_window)
    if not _IS_MAC:
        # No portable equivalent on Linux/X11. Overlay will appear in captures.
        return False
    try:
        from Cocoa import NSApp
    except ImportError:
        print("[WARN] pyobjc-framework-Cocoa not available; overlay is visible to screen capture")
        return False

    # Force the NSWindow to be realized so NSApp.windows() sees it
    tk_window.update_idletasks()
    tk_window.update()

    target_title = tk_window.title()
    NSWindowSharingNone = 0
    # Overlay is visible on every Space simultaneously, including fullscreen apps.
    # Stationary keeps it pinned in place during Mission Control transitions.
    NSWindowCollectionBehaviorCanJoinAllSpaces = 1 << 0
    NSWindowCollectionBehaviorStationary = 1 << 4
    NSWindowCollectionBehaviorFullScreenAuxiliary = 1 << 8
    NSPopUpMenuWindowLevel = 101

    behavior = (
        NSWindowCollectionBehaviorCanJoinAllSpaces
        | NSWindowCollectionBehaviorStationary
        | NSWindowCollectionBehaviorFullScreenAuxiliary
    )

    found_titles = []
    for ns_window in NSApp.windows():
        try:
            t = ns_window.title()
            found_titles.append(repr(t))
            if t == target_title:
                ns_window.setSharingType_(NSWindowSharingNone)
                ns_window.setCollectionBehavior_(behavior)
                ns_window.setLevel_(NSPopUpMenuWindowLevel)
                print(
                    f"[INFO] Overlay '{target_title}' configured: "
                    f"sharing=hidden, collection={behavior}, level={NSPopUpMenuWindowLevel}"
                )
                return ns_window
        except Exception as e:
            found_titles.append(f"<err:{e}>")
            continue
    print(f"[WARN] Could not locate NSWindow named {target_title!r}; saw: {found_titles}")
    return None


def _active_screen_top_right_windows(window_w, window_h, margin=20, top_margin=60):
    """Windows multi-monitor: top-right of whichever monitor the cursor is on,
    using the work area (excludes the taskbar)."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32

        class POINT(ctypes.Structure):
            _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]

        class RECT(ctypes.Structure):
            _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG),
                        ('right', wintypes.LONG), ('bottom', wintypes.LONG)]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [('cbSize', wintypes.DWORD), ('rcMonitor', RECT),
                        ('rcWork', RECT), ('dwFlags', wintypes.DWORD)]

        user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.MonitorFromPoint.argtypes = [POINT, wintypes.DWORD]
        user32.MonitorFromPoint.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]
        user32.GetMonitorInfoW.restype = wintypes.BOOL

        pt = POINT()
        if not user32.GetCursorPos(ctypes.byref(pt)):
            return None
        MONITOR_DEFAULTTONEAREST = 2
        hmon = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
            return None
        rc = info.rcWork
        return (int(rc.right - window_w - margin), int(rc.top + top_margin))
    except Exception as e:
        print(f"[WARN] Windows multi-monitor lookup failed: {e}")
        return None


def _active_screen_top_right(window_w, window_h, margin=20, top_margin=60):
    """Return (x, y) in Tk geometry coords for the top-right of whichever
    screen the mouse cursor is on. Falls back to primary screen on failure."""
    if _IS_WIN:
        return _active_screen_top_right_windows(window_w, window_h, margin, top_margin)
    if not _IS_MAC:
        return None  # Linux: caller falls back to Tk's primary-screen geometry
    try:
        from Cocoa import NSScreen, NSEvent
    except ImportError:
        return None
    try:
        mouse = NSEvent.mouseLocation()  # NSPoint, origin bottom-left of main display
        main_height = NSScreen.mainScreen().frame().size.height
        for screen in NSScreen.screens():
            f = screen.frame()
            if (f.origin.x <= mouse.x <= f.origin.x + f.size.width and
                    f.origin.y <= mouse.y <= f.origin.y + f.size.height):
                # Convert NSScreen (bottom-left, main-relative) -> Tk (top-left from main top)
                tk_x = int(f.origin.x + f.size.width - window_w - margin)
                tk_y = int(main_height - f.origin.y - f.size.height + top_margin)
                return (tk_x, tk_y)
    except Exception as e:
        print(f"[WARN] Active-screen lookup failed: {e}")
    return None


class ResponseOverlay:
    """Creates a transparent overlay window to display AI responses"""

    MINI_SIZE = (140, 46)
    COMPACT_SIZE = (440, 400)
    EXPANDED_SIZE = (780, 620)

    def __init__(self):
        self.window = None
        self.text_widget = None
        self.input_entry = None
        self.pin_text = None  # Text widget for the persistent pinned context
        self.expand_btn = None
        self.minimize_btn = None
        self.history_btn = None
        # Each entry: (frame, pack_kwargs_dict). Hidden when minimized.
        self.body_frames = []
        self.mini_frame = None
        self.on_submit = None  # callback: fn(question_str) — set by agent
        self.history_store = None  # set by agent — local Q&A log for the
                                   # History popup (None = button is inert)
        self._history_window = None  # the open Toplevel, if any
        self.is_visible = True
        self.is_expanded = False
        self.is_minimized = False
        self._pin_save_after_id = None

    def create_window(self):
        """Create the overlay window"""
        if self.window is not None:
            return

        # Create main window
        self.window = tk.Tk()
        self.window.title("Warden")

        # Make the Python app an accessory (improves Spaces behavior) before
        # the NSWindow is fully realized.
        _set_accessory_activation_policy()

        # Window configuration. On macOS we rely on NSWindow.setLevel_ for
        # "always on top" (Tk's -topmost fights with our window level there).
        # On Windows/Linux there's no NSWindow level, so use Tk's -topmost
        # to keep the overlay above other windows — without it the overlay
        # falls to normal z-order and gets buried when another app opens.
        self.window.attributes('-alpha', 0.97)
        if not _IS_MAC:
            self.window.attributes('-topmost', True)
        self.window.resizable(True, True)
        # Tall enough that the input row + buttons are always visible (no
        # "hunting for the writing part by scrolling" — the pen icon also
        # jumps you straight there).
        self.window.minsize(380, 380)

        # Initial size + position (compact, top-right of active screen)
        self._reposition()

        # Style
        self.window.configure(bg=_BG)

        # Title bar with minimize + expand toggles
        title_frame = tk.Frame(self.window, bg=_PANEL, height=46)
        title_frame.pack(fill=tk.X, padx=0, pady=0)

        title_label = tk.Label(
            title_frame,
            text="Warden",
            bg=_PANEL,
            fg=_FG,
            font=_TITLE_FONT,
            pady=12,
        )
        title_label.pack(side=tk.LEFT, padx=16)

        # "Write ↓" affordance — text label + down arrow so the direction
        # is unmistakable (the input row lives at the bottom of the panel).
        # Apple-blue accent so the eye lands on it; click → focus the
        # input field immediately, restoring from minimized if needed.
        self.write_btn = tk.Button(
            title_frame,
            text="Write ↓",
            command=self._jump_to_input,
            bg=_PANEL,
            fg=_ACCENT,
            font=(_UI_FAMILY, 12, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=12,
            cursor='hand2',
            activebackground=_FIELD,
            activeforeground=_ACCENT,
        )
        self.write_btn.pack(side=tk.RIGHT, padx=4)

        # History — opens a small popup listing past Q&A (local SQLite log).
        # Click an entry to render it in the response area. Search-as-you-type.
        self.history_btn = tk.Button(
            title_frame,
            text="History",
            command=self._open_history_window,
            bg=_PANEL,
            fg=_FG_MUTED,
            font=(_UI_FAMILY, 11),
            relief=tk.FLAT,
            bd=0,
            padx=10,
            cursor='hand2',
            activebackground=_FIELD,
            activeforeground=_FG,
        )
        self.history_btn.pack(side=tk.RIGHT, padx=4)

        self.expand_btn = tk.Button(
            title_frame,
            text="⤢",
            command=self.toggle_expand,
            bg=_PANEL,
            fg=_FG_MUTED,
            font=(_UI_FAMILY, 14, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=10,
            cursor='hand2',
            activebackground=_FIELD,
            activeforeground=_FG,
        )
        self.expand_btn.pack(side=tk.RIGHT, padx=4)

        self.minimize_btn = tk.Button(
            title_frame,
            text="—",
            command=self.minimize,
            bg=_PANEL,
            fg=_FG_MUTED,
            font=(_UI_FAMILY, 14, "bold"),
            relief=tk.FLAT,
            bd=0,
            padx=10,
            cursor='hand2',
            activebackground=_FIELD,
            activeforeground=_FG,
        )
        self.minimize_btn.pack(side=tk.RIGHT, padx=4)

        # The minimized "pill" view: a single clickable label that lives in
        # place of the rest of the UI when the user clicks minimize.
        self.mini_frame = tk.Frame(self.window, bg=_BG)
        mini_label = tk.Label(
            self.mini_frame,
            text="Warden",
            bg=_BG,
            fg=_FG,
            font=_LABEL_FONT,
            cursor='hand2',
        )
        mini_label.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)
        mini_label.bind('<Button-1>', lambda e: self.restore())
        # mini_frame is NOT packed by default — only when minimized.

        # Pinned-context box: persistent text included with every request.
        # Stays put until the user edits it. Saved to disk so it survives
        # restarts.
        # === Input row — moved to the TOP of the overlay body so it's
        # always visible no matter how short the overlay is. Click "Write ↓"
        # or press Ctrl+Alt+W (cross-platform) → cursor lands here. No
        # resize, no scrolling, no hunting. ====================================
        input_frame = tk.Frame(self.window, bg=_BG)
        input_pack = dict(fill=tk.X, padx=14, pady=(12, 0))
        input_frame.pack(**input_pack)
        self.body_frames.append((input_frame, input_pack))

        self.input_entry = tk.Entry(
            input_frame,
            bg=_FIELD,
            fg=_FG,
            insertbackground=_FG,
            font=_BODY_FONT,
            relief=tk.FLAT,
            highlightthickness=0,
            borderwidth=0,
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=9, padx=(0, 8))
        self.input_entry.bind('<Return>', lambda e: self._submit_question())

        send_btn = tk.Button(
            input_frame,
            text="Send",
            command=self._submit_question,
            bg=_ACCENT,
            fg="#ffffff",
            font=_BTN_FONT_BOLD,
            relief=tk.FLAT,
            padx=22,
            pady=8,
            cursor='hand2',
            activebackground="#1c8aff",
            activeforeground="#ffffff",
            borderwidth=0,
        )
        send_btn.pack(side=tk.RIGHT)

        # Pinned-context box — below the input row, above the response.
        pin_frame = tk.Frame(self.window, bg=_BG)
        pin_pack = dict(fill=tk.X, padx=14, pady=(12, 0))
        pin_frame.pack(**pin_pack)
        pin_header = tk.Label(
            pin_frame,
            text="📌  Pinned context (sent every request)",
            bg=_BG,
            fg=_FG_MUTED,
            font=_MUTED_FONT,
            anchor='w',
        )
        pin_header.pack(fill=tk.X, pady=(0, 4))
        self.pin_text = tk.Text(
            pin_frame,
            height=3,
            wrap=tk.WORD,
            bg=_FIELD_HI,
            fg=_FG,
            insertbackground=_FG,
            font=_LABEL_FONT,
            relief=tk.FLAT,
            padx=10,
            pady=8,
            spacing1=1,
            spacing3=2,
            highlightthickness=0,
        )
        self.pin_text.pack(fill=tk.X)
        self.pin_text.bind('<KeyRelease>', lambda e: self._schedule_pin_save())
        # Load any previously-saved pin
        prior = self._load_pin_from_disk()
        if prior:
            self.pin_text.insert('1.0', prior)
        self.body_frames.append((pin_frame, pin_pack))

        # Text display area — the main response panel. Bigger body type,
        # generous padding, and line spacing for a Claude-style read.
        text_frame = tk.Frame(self.window, bg=_BG)
        text_pack = dict(fill=tk.BOTH, expand=True, padx=14, pady=12)
        text_frame.pack(**text_pack)
        self.body_frames.append((text_frame, text_pack))

        self.text_widget = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            bg=_FIELD,
            fg=_FG,
            font=_BODY_FONT_BIG,
            insertbackground=_FG,
            relief=tk.FLAT,
            padx=16,
            pady=14,
            spacing1=2,
            spacing2=1,
            spacing3=5,
            highlightthickness=0,
            borderwidth=0,
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)

        # Button frame
        button_frame = tk.Frame(self.window, bg=_BG)
        button_pack = dict(fill=tk.X, padx=14, pady=(0, 14))
        button_frame.pack(**button_pack)
        self.body_frames.append((button_frame, button_pack))

        # Minimize-from-button-row (matches the "—" in the title bar)
        close_btn = tk.Button(
            button_frame,
            text="Minimize (ESC)",
            command=self.minimize,
            bg=_BTN_BG,
            fg=_FG,
            font=_BTN_FONT,
            relief=tk.FLAT,
            padx=22,
            pady=9,
            cursor='hand2',
            activebackground="#4a4a4a",
            activeforeground=_FG,
            borderwidth=0,
        )
        close_btn.pack(side=tk.RIGHT)

        # Copy button
        copy_btn = tk.Button(
            button_frame,
            text="Copy",
            command=self.copy_to_clipboard,
            bg=_BTN_BG,
            fg=_FG,
            font=_BTN_FONT,
            relief=tk.FLAT,
            padx=22,
            pady=9,
            cursor='hand2',
            activebackground="#4a4a4a",
            activeforeground=_FG,
            borderwidth=0,
        )
        copy_btn.pack(side=tk.RIGHT, padx=6)

        # Keyboard bindings
        self.window.bind('<Escape>', lambda e: self.minimize())
        self.window.bind('<Control-c>', lambda e: self.copy_to_clipboard())

        # Closing the red X minimizes instead of killing the client
        self.window.protocol("WM_DELETE_WINDOW", self.minimize)

        # Apply screen-capture exclusion + Spaces / level attributes.
        # The window is shown immediately (no withdraw) — staying always
        # visible avoids the show/hide → wrong-Space problem.
        _exclude_from_screen_capture(self.window)
        # Re-apply attributes a few times after Tk finishes laying things
        # out, in case Tk re-sets defaults during initial event dispatch.
        for delay_ms in (200, 600, 1500):
            self.window.after(delay_ms, lambda: _exclude_from_screen_capture(self.window))

    def show(self, content, metadata=None):
        """Update overlay content. The window is always visible — this just
        replaces text and ensures we're not in minimized state."""
        if self.window is None:
            self.create_window()

        # Restore from minimized if needed
        if self.is_minimized:
            self.restore()

        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(1.0, content)

        if metadata:
            self.text_widget.insert(tk.END, f"\n\n{'─'*50}\n")
            self.text_widget.insert(tk.END, f"Model: {metadata.get('model', 'unknown')}\n")
            self.text_widget.insert(tk.END, f"Tokens: {metadata.get('tokens_used', 'unknown')}\n")
            self.text_widget.insert(tk.END, f"Time: {metadata.get('timestamp', 'unknown')}\n")

        # Bring it to front of the z-order without stealing focus.
        # NSWindow attributes (sharing, collection, level) were set at
        # create_window and are sticky — re-applying on every show caused
        # PyObjC native crashes after many calls.
        self.window.lift()
        # On Windows/Linux re-assert topmost: another app going topmost can
        # otherwise leave our overlay stuck behind it.
        if not _IS_MAC:
            try:
                self.window.attributes('-topmost', True)
            except Exception:
                pass

    def minimize(self):
        """Collapse the overlay to a tiny pill in the corner. The window
        stays visible — it just shrinks so it doesn't cover your work."""
        if not self.window or self.is_minimized:
            return
        for frame, _ in self.body_frames:
            frame.pack_forget()
        self.mini_frame.pack(fill=tk.BOTH, expand=True)
        self.is_minimized = True
        w, h = self.MINI_SIZE
        self.window.minsize(w, h)
        pos = _active_screen_top_right(w, h)
        if pos:
            x, y = pos
        else:
            x = self.window.winfo_screenwidth() - w - 20
            y = 60
        self.window.geometry(f"{w}x{h}+{x}+{y}")

    def restore(self):
        """Expand from the minimized pill back to the full overlay."""
        if not self.window or not self.is_minimized:
            return
        self.mini_frame.pack_forget()
        for frame, pack_kwargs in self.body_frames:
            frame.pack(**pack_kwargs)
        self.is_minimized = False
        self.window.minsize(300, 220)
        self._reposition()

    def _reposition(self):
        """Resize to current compact/expanded size and place on the active screen."""
        if not self.window:
            return
        w, h = self.EXPANDED_SIZE if self.is_expanded else self.COMPACT_SIZE
        pos = _active_screen_top_right(w, h)
        if pos:
            x, y = pos
        else:
            x = self.window.winfo_screenwidth() - w - 20
            y = 60
        self.window.geometry(f"{w}x{h}+{x}+{y}")

    def toggle_expand(self):
        """Switch between compact and expanded sizes."""
        self.is_expanded = not self.is_expanded
        if self.expand_btn is not None:
            self.expand_btn.configure(text="⤡" if self.is_expanded else "⤢")
        self._reposition()

    # --- Pinned-context persistence ---------------------------------------

    @staticmethod
    def _pin_storage_path():
        import os
        if _IS_MAC:
            base = os.path.expanduser('~/Library/Application Support/TextKit')
        elif _IS_WIN:
            base = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'TextKit')
        else:
            base = os.path.join(
                os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config')),
                'textkit',
            )
        try:
            os.makedirs(base, exist_ok=True)
        except Exception:
            pass
        return os.path.join(base, 'pin.txt')

    def _load_pin_from_disk(self):
        try:
            with open(self._pin_storage_path(), 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return ''
        except Exception as e:
            print(f"[WARN] failed to load pin: {e}")
            return ''

    def _schedule_pin_save(self):
        if self._pin_save_after_id is not None:
            try:
                self.window.after_cancel(self._pin_save_after_id)
            except Exception:
                pass
        self._pin_save_after_id = self.window.after(500, self._save_pin)

    def _save_pin(self):
        self._pin_save_after_id = None
        try:
            content = self.get_pin()
            with open(self._pin_storage_path(), 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"[WARN] failed to save pin: {e}")

    def get_pin(self):
        """Return the current pinned-context text (stripped)."""
        if self.pin_text is None:
            return ''
        return self.pin_text.get('1.0', 'end-1c').strip()

    def _open_history_window(self):
        """Pop a small searchable list of past Q&A. Click an entry to
        render it in the main response area. Cheap and local — never
        re-queries the model."""
        if self.window is None or self.history_store is None:
            return

        # If one is already open, just bring it forward.
        if self._history_window is not None:
            try:
                if self._history_window.winfo_exists():
                    self._history_window.deiconify()
                    self._history_window.lift()
                    self._history_window.focus_force()
                    return
            except Exception:
                pass
            self._history_window = None

        win = tk.Toplevel(self.window)
        self._history_window = win
        win.title("Warden — History")
        win.configure(bg=_BG)
        win.geometry("560x540")
        if not _IS_MAC:
            try:
                win.attributes('-topmost', True)
            except Exception:
                pass

        # Header / search row
        header = tk.Frame(win, bg=_BG)
        header.pack(fill=tk.X, padx=14, pady=(14, 8))
        tk.Label(
            header,
            text="Search",
            bg=_BG,
            fg=_FG_MUTED,
            font=_MUTED_FONT,
        ).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = tk.Entry(
            header,
            textvariable=search_var,
            bg=_FIELD,
            fg=_FG,
            insertbackground=_FG,
            font=_BODY_FONT,
            relief=tk.FLAT,
            highlightthickness=0,
            borderwidth=0,
        )
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(10, 0), ipady=6)
        search_entry.focus_set()

        count_label = tk.Label(
            win,
            text="",
            bg=_BG,
            fg=_FG_MUTED,
            font=_MUTED_FONT,
            anchor='w',
        )
        count_label.pack(fill=tk.X, padx=14, pady=(0, 6))

        # List + scrollbar
        list_frame = tk.Frame(win, bg=_BG)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 14))
        listbox = tk.Listbox(
            list_frame,
            bg=_FIELD,
            fg=_FG,
            font=_BODY_FONT,
            selectmode=tk.SINGLE,
            relief=tk.FLAT,
            highlightthickness=0,
            borderwidth=0,
            activestyle='none',
            selectbackground=_ACCENT,
            selectforeground='#ffffff',
        )
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(list_frame, command=listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=sb.set)

        # Holds the entries currently displayed, indexed to listbox rows.
        state = {'entries': []}

        def refresh(*_):
            q = search_var.get().strip()
            entries = (
                self.history_store.search(q, limit=200)
                if q else self.history_store.recent(limit=200)
            )
            state['entries'] = entries
            listbox.delete(0, tk.END)
            for e in entries:
                listbox.insert(tk.END, e.short_label())
            total = self.history_store.count()
            if q:
                count_label.configure(
                    text=f"{len(entries)} match(es) of {total} total."
                )
            else:
                count_label.configure(text=f"{total} total entries.")

        def on_select(_event=None):
            sel = listbox.curselection()
            if not sel:
                return
            entry = state['entries'][sel[0]]
            from datetime import datetime as _dt
            when = _dt.fromtimestamp(entry.ts).strftime("%Y-%m-%d %H:%M")
            content = (
                f"[{when}]"
                + (f"\n\nQ: {entry.question}" if entry.question else "")
                + f"\n\n{entry.answer}"
            )
            if self.text_widget is not None:
                self.text_widget.delete(1.0, tk.END)
                self.text_widget.insert(1.0, content)
                self.text_widget.see('1.0')
            self.window.lift()
            if not _IS_MAC:
                try:
                    self.window.attributes('-topmost', True)
                except Exception:
                    pass

        def on_close():
            self._history_window = None
            try:
                win.destroy()
            except Exception:
                pass

        listbox.bind('<<ListboxSelect>>', on_select)
        search_var.trace_add('write', refresh)
        win.protocol('WM_DELETE_WINDOW', on_close)
        win.bind('<Escape>', lambda _e: on_close())
        refresh()

    def _jump_to_input(self):
        """"Write ↓" click → focus the input box. That's it.

        Restores from the minimized pill if needed (otherwise focusing
        a hidden field does nothing visible), scrolls the response to
        the end so the input is the visual anchor, then puts the
        cursor straight in the input. No resizing — the user keeps the
        overlay at whatever size they like.
        """
        if self.window is None:
            return
        if self.is_minimized:
            self.restore()
        if self.text_widget is not None:
            try:
                self.text_widget.see('end')
            except Exception:
                pass
        if self.input_entry is not None:
            self.input_entry.focus_force()

    def _submit_question(self):
        """Send whatever's in the input field to the agent's callback."""
        if not self.input_entry or not self.on_submit:
            return
        question = self.input_entry.get().strip()
        if not question:
            return
        self.input_entry.delete(0, tk.END)
        # Indicate that a request is in flight
        self.text_widget.delete(1.0, tk.END)
        self.text_widget.insert(1.0, f"Asking: {question}\n\n(thinking...)")
        try:
            self.on_submit(question)
        except Exception as e:
            print(f"[ERROR] on_submit callback failed: {e}")

    def copy_to_clipboard(self):
        """Copy content to clipboard"""
        if self.text_widget:
            content = self.text_widget.get(1.0, tk.END)
            self.window.clipboard_clear()
            self.window.clipboard_append(content)
            print("[INFO] Content copied to clipboard")

    def destroy(self):
        """Destroy the window"""
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass  # Already destroyed (e.g. user closed via X)
            self.window = None
            self.text_widget = None
            self.is_visible = False

    def run_in_thread(self, content, metadata=None):
        """Show overlay in a separate thread"""
        def show_window():
            self.show(content, metadata)
            if self.window:
                self.window.mainloop()

        thread = threading.Thread(target=show_window, daemon=True)
        thread.start()


class MinimalOverlay:
    """Minimal notification-style overlay"""

    def __init__(self):
        self.window = None

    def show(self, content, duration=5000):
        """
        Show a minimal notification overlay

        Args:
            content: Text to display
            duration: Time to show in milliseconds (0 = stay until clicked)
        """
        # Create window
        self.window = tk.Tk()
        self.window.title("")

        # Remove window decorations
        self.window.overrideredirect(True)

        # Window configuration
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.9)

        # Size and position (bottom right)
        window_width = 400
        window_height = 150

        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = screen_width - window_width - 20
        y = screen_height - window_height - 50

        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Style
        self.window.configure(bg='#2d2d2d')

        # Content
        label = tk.Label(
            self.window,
            text=content,
            bg='#2d2d2d',
            fg='#ffffff',
            font=('Arial', 10),
            wraplength=window_width - 40,
            justify=tk.LEFT,
            padx=20,
            pady=20
        )
        label.pack(fill=tk.BOTH, expand=True)

        # Click to close
        self.window.bind('<Button-1>', lambda e: self.close())
        label.bind('<Button-1>', lambda e: self.close())

        # Auto-close after duration
        if duration > 0:
            self.window.after(duration, self.close)

        self.window.mainloop()

    def close(self):
        """Close the overlay"""
        if self.window:
            self.window.destroy()
            self.window = None


# Test the overlay
if __name__ == "__main__":
    import time

    print("Testing overlay display...")

    # Test main overlay
    overlay = ResponseOverlay()

    test_content = """This is a test of the AI assistant overlay!

Here's some sample content that would normally come from Claude:

1. First point
2. Second point
3. Third point

Pretty cool, right?"""

    test_metadata = {
        'model': 'claude-sonnet-4-20250514',
        'tokens_used': 150,
        'timestamp': '2025-12-22 23:00:00'
    }

    print("Showing overlay...")
    overlay.show(test_content, test_metadata)

    # Keep it open
    if overlay.window:
        overlay.window.mainloop()
