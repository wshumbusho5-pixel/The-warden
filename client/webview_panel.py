"""
Embed a native WKWebView for the Warden response area.

macOS only. Windows will get its own WebView2-based counterpart later.

Reparenting a WKWebView under a Tk widget's NSView is finicky and
crashes in current Tk builds because Tk hands out different pointer
types depending on the widget lifecycle. Instead we take a stabler
route: give WKWebView its own borderless NSWindow that is added as a
CHILD of the Tk overlay's NSWindow. The child window tracks the
parent's z-order, moves with it, and inherits our
NSWindowSharingNone flag — so from the user's point of view it looks
like the response panel lives inside the overlay, and from macOS's
point of view screenshots and screen shares blank both windows.

If the WebKit binding isn't available, this module raises ImportError
at import time; the overlay treats that as "no webview, keep using the
old Tk text widget" so the client still runs.
"""

import os
import sys
import threading

if sys.platform != "darwin":
    raise ImportError("webview_panel is macOS-only; use Tk fallback elsewhere.")

from AppKit import (
    NSApplication,
    NSWindow,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    NSMakeRect,
    NSColor,
    NSViewWidthSizable,
    NSViewHeightSizable,
    NSWindowAbove,
)
from Foundation import NSURL
from WebKit import (
    WKWebView,
    WKWebViewConfiguration,
    WKPreferences,
)


NSWindowSharingNone = 0


def _assets_dir():
    if hasattr(sys, "_MEIPASS"):
        base = os.path.join(sys._MEIPASS, "client", "webview_assets")
        if os.path.isdir(base):
            return base
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "webview_assets")


class WebviewPanel:
    """WKWebView living in a borderless child NSWindow docked onto the
    Tk overlay's response area.

    Args:
        tk_frame: the Tk Frame that "would" have held the response widget.
            We measure it (in screen coords) and place the webview window
            over it, then keep them synced.
        parent_tk_window: the Tk root window (used to get its NSWindow and
            wire the parent-child relationship).
    """

    def __init__(self, tk_frame, parent_tk_window):
        self._tk_frame = tk_frame
        self._parent_tk_window = parent_tk_window
        self._ready = False
        self._pending_calls = []
        self._pending_lock = threading.Lock()
        self._child_window = None
        self._web_view = None
        self._resync_after_id = None

        NSApplication.sharedApplication()

        # Find the parent Tk root's NSWindow — Tk on macOS uses NSApp.windows()
        # keyed by title, same trick overlay_display.py uses.
        parent_ns_window = self._find_parent_ns_window()
        if parent_ns_window is None:
            raise ImportError("could not locate parent NSWindow for Tk root")

        # Build a borderless child NSWindow sized to the frame.
        frame_rect = self._compute_frame_rect()
        child = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame_rect,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False,
        )
        child.setOpaque_(True)
        child.setBackgroundColor_(
            NSColor.colorWithRed_green_blue_alpha_(
                0x22/255.0, 0x22/255.0, 0x22/255.0, 1.0
            )
        )
        # Same moat flag as the parent — belt and braces.
        child.setSharingType_(NSWindowSharingNone)
        # Ignore mouse-drag on the borderless frame; we want interactions
        # to fall through to the webview content itself.
        child.setMovable_(False)

        config = WKWebViewConfiguration.alloc().init()
        prefs = WKPreferences.alloc().init()
        try:
            prefs.setValue_forKey_(True, "allowFileAccessFromFileURLs")
            prefs.setValue_forKey_(True, "allowUniversalAccessFromFileURLs")
        except Exception:
            pass
        config.setPreferences_(prefs)

        content_view = child.contentView()
        web_view = WKWebView.alloc().initWithFrame_configuration_(
            content_view.bounds(), config
        )
        web_view.setAutoresizingMask_(
            NSViewWidthSizable | NSViewHeightSizable
        )
        try:
            web_view.setValue_forKey_(False, "drawsBackground")
        except Exception:
            pass
        content_view.addSubview_(web_view)

        # Attach as a child of the Tk root's NSWindow so it moves with it,
        # closes with it, and lives above it in z-order.
        parent_ns_window.addChildWindow_ordered_(child, NSWindowAbove)

        # Load the shell HTML.
        html_path = os.path.join(_assets_dir(), "index.html")
        if not os.path.isfile(html_path):
            raise ImportError(f"webview shell missing: {html_path}")
        url = NSURL.fileURLWithPath_(html_path)
        base = NSURL.fileURLWithPath_isDirectory_(_assets_dir(), True)
        web_view.loadFileURL_allowingReadAccessToURL_(url, base)

        self._child_window = child
        self._web_view = web_view

        # Keep the child window docked onto the Tk frame's screen rect.
        tk_frame.bind("<Configure>", lambda _e: self._schedule_resync())
        parent_tk_window.bind("<Configure>", lambda _e: self._schedule_resync())

        self._schedule_resync()
        self._schedule_ready_check()

    # ------- public API ----------------------------------------------------

    def render_markdown(self, markdown_text):
        self._call_js("renderMarkdown", markdown_text)

    def set_thinking(self, question):
        self._call_js("setThinking", question or "")

    def show_message(self, text):
        self._call_js("renderMarkdown", text or "")

    def destroy(self):
        """Release the child window. Called during overlay teardown."""
        try:
            if self._child_window is not None:
                self._child_window.orderOut_(None)
                self._child_window.close()
        except Exception:
            pass
        self._child_window = None
        self._web_view = None

    # ------- internals -----------------------------------------------------

    def _find_parent_ns_window(self):
        try:
            from AppKit import NSApp
        except Exception:
            return None
        parent_title = self._parent_tk_window.title()
        for w in NSApp.windows():
            try:
                if w.title() == parent_title:
                    return w
            except Exception:
                continue
        return None

    def _compute_frame_rect(self):
        """Return the child window's screen rect matching the Tk frame."""
        self._parent_tk_window.update_idletasks()
        # Tk widget screen coords, in top-left origin.
        x = self._tk_frame.winfo_rootx()
        y = self._tk_frame.winfo_rooty()
        w = max(1, self._tk_frame.winfo_width())
        h = max(1, self._tk_frame.winfo_height())
        # Convert to Cocoa's bottom-left origin using main screen height.
        try:
            from AppKit import NSScreen
            main_h = NSScreen.mainScreen().frame().size.height
        except Exception:
            main_h = 0
        return NSMakeRect(x, main_h - y - h, w, h)

    def _schedule_resync(self):
        """Coalesce a repositioning of the child window."""
        try:
            if self._resync_after_id is not None:
                self._parent_tk_window.after_cancel(self._resync_after_id)
        except Exception:
            pass
        try:
            self._resync_after_id = self._parent_tk_window.after(
                30, self._resync_now
            )
        except Exception:
            self._resync_now()

    def _resync_now(self):
        self._resync_after_id = None
        if self._child_window is None:
            return
        rect = self._compute_frame_rect()
        try:
            self._child_window.setFrame_display_(rect, True)
        except Exception:
            pass

    def _schedule_ready_check(self):
        def _mark_ready():
            self._ready = True
            with self._pending_lock:
                pending, self._pending_calls = self._pending_calls, []
            for fn, arg in pending:
                self._exec_js(fn, arg)
        try:
            self._parent_tk_window.after(300, _mark_ready)
        except Exception:
            _mark_ready()

    def _call_js(self, fn, arg):
        if not self._ready:
            with self._pending_lock:
                self._pending_calls.append((fn, arg))
            return
        try:
            self._parent_tk_window.after(0, lambda: self._exec_js(fn, arg))
        except Exception:
            self._exec_js(fn, arg)

    def _exec_js(self, fn, arg):
        if self._web_view is None:
            return
        js_arg = _js_string_literal(arg if arg is not None else "")
        script = f"window.{fn} && window.{fn}({js_arg});"
        self._web_view.evaluateJavaScript_completionHandler_(script, None)


def _js_string_literal(s):
    import json
    return json.dumps(s, ensure_ascii=False)
