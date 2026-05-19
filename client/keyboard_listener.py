"""
Cross-platform global hotkey listener.

macOS: Carbon's RegisterEventHotKey — no Accessibility permission needed.
  pynput / CGEventTap would require Accessibility, which macOS grants per
  code-signing hash and so breaks for ad-hoc-signed PyInstaller bundles
  every time you rebuild. Carbon's hotkey API doesn't see other keys, so
  it sidesteps that whole permission.

Windows: user32's RegisterHotKey on a dedicated message-loop thread.
  hwnd=NULL routes WM_HOTKEY to the thread's message queue, so the same
  thread that registers must also pump messages. No special permissions.

Other platforms: a stub that loudly refuses — the rest of the client still
runs, just without global hotkeys.
"""

import ctypes
import sys
import threading
from datetime import datetime


_IS_MAC = sys.platform == 'darwin'
_IS_WIN = sys.platform.startswith('win')


# =============================================================================
# macOS Carbon implementation
# =============================================================================

if _IS_MAC:
    import ctypes.util

    def _fourcc(s):
        return (ord(s[0]) << 24) | (ord(s[1]) << 16) | (ord(s[2]) << 8) | ord(s[3])

    CMD_KEY     = 1 << 8       # 256
    SHIFT_KEY   = 1 << 9       # 512
    OPTION_KEY  = 1 << 11      # 2048
    CONTROL_KEY = 1 << 12      # 4096

    K_EVENT_CLASS_KEYBOARD   = _fourcc('keyb')
    K_EVENT_HOTKEY_PRESSED   = 5
    K_EVENT_PARAM_DIRECT_OBJ = _fourcc('----')
    TYPE_EVENT_HOTKEY_ID     = _fourcc('hkid')

    MAC_MODIFIER_MAP = {
        'cmd': CMD_KEY, 'command': CMD_KEY, 'super': CMD_KEY, 'win': CMD_KEY,
        'shift': SHIFT_KEY,
        'option': OPTION_KEY, 'opt': OPTION_KEY, 'alt': OPTION_KEY,
        'ctrl': CONTROL_KEY, 'control': CONTROL_KEY,
    }

    # macOS virtual key codes (kVK_ANSI_*)
    MAC_KEY_CODES = {
        'a': 0, 's': 1, 'd': 2, 'f': 3, 'h': 4, 'g': 5, 'z': 6, 'x': 7,
        'c': 8, 'v': 9, 'b': 11, 'q': 12, 'w': 13, 'e': 14, 'r': 15,
        'y': 16, 't': 17, 'o': 31, 'u': 32, 'i': 34, 'p': 35, 'l': 37,
        'j': 38, 'k': 40, 'n': 45, 'm': 46,
        '1': 18, '2': 19, '3': 20, '4': 21, '5': 23, '6': 22, '7': 26,
        '8': 28, '9': 25, '0': 29,
        'space': 49, 'tab': 48, 'return': 36, 'enter': 36, 'escape': 53,
        'esc': 53, 'delete': 51, 'backspace': 51,
        'left': 123, 'right': 124, 'down': 125, 'up': 126,
        'f1': 122, 'f2': 120, 'f3': 99, 'f4': 118, 'f5': 96, 'f6': 97,
        'f7': 98, 'f8': 100, 'f9': 101, 'f10': 109, 'f11': 103, 'f12': 111,
    }

    _carbon_path = ctypes.util.find_library('Carbon')
    _carbon = ctypes.cdll.LoadLibrary(_carbon_path) if _carbon_path else None

    class _EventHotKeyID(ctypes.Structure):
        _fields_ = [('signature', ctypes.c_uint32), ('id', ctypes.c_uint32)]

    class _EventTypeSpec(ctypes.Structure):
        _fields_ = [('eventClass', ctypes.c_uint32), ('eventKind', ctypes.c_uint32)]

    _EventHandlerProc = ctypes.CFUNCTYPE(
        ctypes.c_int32,    # OSStatus
        ctypes.c_void_p,   # EventHandlerCallRef nextHandler
        ctypes.c_void_p,   # EventRef event
        ctypes.c_void_p,   # void *userData
    )

    if _carbon is not None:
        _carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
        _carbon.RegisterEventHotKey.argtypes = [
            ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID,
            ctypes.c_void_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        _carbon.RegisterEventHotKey.restype = ctypes.c_int32
        _carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        _carbon.UnregisterEventHotKey.restype = ctypes.c_int32
        _carbon.InstallEventHandler.argtypes = [
            ctypes.c_void_p, _EventHandlerProc, ctypes.c_uint32,
            ctypes.POINTER(_EventTypeSpec), ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        _carbon.InstallEventHandler.restype = ctypes.c_int32
        _carbon.RemoveEventHandler.argtypes = [ctypes.c_void_p]
        _carbon.RemoveEventHandler.restype = ctypes.c_int32
        _carbon.GetEventParameter.argtypes = [
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        _carbon.GetEventParameter.restype = ctypes.c_int32

    def _parse_mac(hotkey_str):
        """'ctrl+alt+a' -> (modifier_flags, key_code). (None, None) on parse error."""
        mods = 0
        key_code = None
        for p in (p.strip().lower() for p in hotkey_str.split('+')):
            if p in MAC_MODIFIER_MAP:
                mods |= MAC_MODIFIER_MAP[p]
            elif p in MAC_KEY_CODES:
                key_code = MAC_KEY_CODES[p]
            else:
                return None, None
        if key_code is None:
            return None, None
        return mods, key_code

    class _MacKeyboardListener:
        """Global hotkey listener using Carbon. No Accessibility permission needed."""

        SIGNATURE = _fourcc('TxKt')

        def __init__(self, callback=None, hotkey='ctrl+alt+a', bindings=None):
            if bindings:
                self.bindings = dict(bindings)
            else:
                self.bindings = {hotkey: callback} if callback else {}
            self.hotkey = hotkey
            self.running = False
            self.activation_count = 0
            self._handler_ref = None
            self._handler_cb = None  # keep CFUNCTYPE alive
            self._hk_refs = []
            self._id_to_binding = {}

        def set_callback(self, callback):
            self.bindings = {self.hotkey: callback}

        def _on_event(self, _next, event, _user):
            try:
                hk_id = _EventHotKeyID()
                err = _carbon.GetEventParameter(
                    event,
                    K_EVENT_PARAM_DIRECT_OBJ,
                    TYPE_EVENT_HOTKEY_ID,
                    None,
                    ctypes.sizeof(_EventHotKeyID),
                    None,
                    ctypes.byref(hk_id),
                )
                if err == 0 and hk_id.signature == self.SIGNATURE:
                    binding = self._id_to_binding.get(hk_id.id)
                    if binding:
                        hk_str, cb = binding
                        self.activation_count += 1
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        print(f"\n[{ts}] 🔥 Hotkey activated! ({hk_str})")
                        if cb:
                            threading.Thread(target=cb, daemon=True).start()
            except Exception as e:
                print(f"[ERROR] hotkey handler: {e}")
            return 0  # noErr

        def start(self):
            if self.running:
                print("[WARNING] Listener already running")
                return
            if not self.bindings:
                print("[WARNING] No hotkey bindings configured")
                return
            if _carbon is None:
                print("[ERROR] Carbon framework not available — global hotkeys disabled")
                return

            target = _carbon.GetApplicationEventTarget()

            types = (_EventTypeSpec * 1)()
            types[0].eventClass = K_EVENT_CLASS_KEYBOARD
            types[0].eventKind = K_EVENT_HOTKEY_PRESSED

            self._handler_cb = _EventHandlerProc(self._on_event)
            handler_ref = ctypes.c_void_p()
            err = _carbon.InstallEventHandler(
                target, self._handler_cb, 1, types, None, ctypes.byref(handler_ref)
            )
            if err != 0:
                print(f"[ERROR] InstallEventHandler failed (OSStatus={err})")
                return
            self._handler_ref = handler_ref

            next_id = 1
            for hk_str, cb in self.bindings.items():
                print(f"[INFO] Registering hotkey: {hk_str}")
                mods, key_code = _parse_mac(hk_str)
                if key_code is None:
                    print(f"[ERROR] Could not parse hotkey '{hk_str}'")
                    continue
                hk_id = _EventHotKeyID()
                hk_id.signature = self.SIGNATURE
                hk_id.id = next_id
                hk_ref = ctypes.c_void_p()
                err = _carbon.RegisterEventHotKey(
                    key_code, mods, hk_id, target, 0, ctypes.byref(hk_ref)
                )
                if err != 0:
                    print(f"[ERROR] RegisterEventHotKey failed for '{hk_str}' (OSStatus={err})")
                    continue
                self._hk_refs.append(hk_ref)
                self._id_to_binding[next_id] = (hk_str, cb)
                next_id += 1

            self.running = True
            print(f"[INFO] Keyboard listener started — {len(self._id_to_binding)} hotkey(s) via Carbon")
            for hk_str in self.bindings:
                print(f"[INFO] Press {hk_str} to activate AI assistant")
            print(f"[INFO] Press Ctrl+C to stop")

        def stop(self):
            if not self.running:
                return
            for ref in self._hk_refs:
                try:
                    _carbon.UnregisterEventHotKey(ref)
                except Exception:
                    pass
            self._hk_refs = []
            if self._handler_ref is not None:
                try:
                    _carbon.RemoveEventHandler(self._handler_ref)
                except Exception:
                    pass
                self._handler_ref = None
            self._id_to_binding = {}
            self.running = False
            print("[INFO] Keyboard listener stopped")
            print(f"[INFO] Total activations: {self.activation_count}")

        def wait(self):
            # Carbon events fire on the main thread's run loop; the Tk
            # mainloop in agent.start_background_mode keeps it alive.
            pass

        def change_hotkey(self, new_hotkey):
            was_running = self.running
            if was_running:
                self.stop()
            cb = list(self.bindings.values())[0] if self.bindings else None
            self.bindings = {new_hotkey: cb}
            self.hotkey = new_hotkey
            if was_running:
                self.start()
            print(f"[INFO] Hotkey changed to: {new_hotkey}")


# =============================================================================
# Windows user32 implementation
# =============================================================================

if _IS_WIN:
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    WM_HOTKEY = 0x0312
    WM_QUIT   = 0x0012

    MOD_ALT       = 0x0001
    MOD_CONTROL   = 0x0002
    MOD_SHIFT     = 0x0004
    MOD_WIN       = 0x0008
    MOD_NOREPEAT  = 0x4000

    WIN_MODIFIER_MAP = {
        'ctrl': MOD_CONTROL, 'control': MOD_CONTROL,
        'alt': MOD_ALT, 'option': MOD_ALT, 'opt': MOD_ALT,
        'shift': MOD_SHIFT,
        'win': MOD_WIN, 'super': MOD_WIN, 'cmd': MOD_WIN, 'command': MOD_WIN,
    }

    # Windows virtual-key codes
    WIN_KEY_CODES = {
        **{chr(c).lower(): c for c in range(0x41, 0x5B)},  # A-Z -> 0x41-0x5A
        **{str(d): 0x30 + d for d in range(10)},           # 0-9 -> 0x30-0x39
        **{f'f{i}': 0x6F + i for i in range(1, 25)},       # F1-F24 -> 0x70-0x87
        'space': 0x20, 'tab': 0x09, 'return': 0x0D, 'enter': 0x0D,
        'escape': 0x1B, 'esc': 0x1B, 'backspace': 0x08, 'delete': 0x2E,
        'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
        'home': 0x24, 'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22,
        'insert': 0x2D,
    }

    _user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.UnregisterHotKey.restype = wintypes.BOOL
    _user32.GetMessageW.argtypes = [
        ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
    ]
    _user32.GetMessageW.restype = ctypes.c_int  # signed: returns -1 on error
    _user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.TranslateMessage.restype = wintypes.BOOL
    _user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
    _user32.DispatchMessageW.restype = ctypes.c_long
    _user32.PostThreadMessageW.argtypes = [
        wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    ]
    _user32.PostThreadMessageW.restype = wintypes.BOOL
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    _kernel32.GetLastError.restype = wintypes.DWORD

    def _parse_win(hotkey_str):
        """'ctrl+alt+a' -> (modifier_flags, vk_code). (None, None) on parse error."""
        mods = 0
        vk = None
        for p in (p.strip().lower() for p in hotkey_str.split('+')):
            if p in WIN_MODIFIER_MAP:
                mods |= WIN_MODIFIER_MAP[p]
            elif p in WIN_KEY_CODES:
                vk = WIN_KEY_CODES[p]
            else:
                return None, None
        if vk is None:
            return None, None
        return mods, vk

    class _WindowsKeyboardListener:
        """Global hotkey listener using Win32 RegisterHotKey. No special permission."""

        def __init__(self, callback=None, hotkey='ctrl+alt+a', bindings=None):
            if bindings:
                self.bindings = dict(bindings)
            else:
                self.bindings = {hotkey: callback} if callback else {}
            self.hotkey = hotkey
            self.running = False
            self.activation_count = 0
            self._thread = None
            self._thread_id = None
            self._id_to_binding = {}
            self._ready = None

        def set_callback(self, callback):
            self.bindings = {self.hotkey: callback}

        def _run(self):
            # RegisterHotKey with hwnd=NULL routes WM_HOTKEY to the calling
            # thread's queue — so we must register and pump from the same thread.
            self._thread_id = _kernel32.GetCurrentThreadId()
            next_id = 1
            for hk_str, cb in self.bindings.items():
                print(f"[INFO] Registering hotkey: {hk_str}")
                mods, vk = _parse_win(hk_str)
                if vk is None:
                    print(f"[ERROR] Could not parse hotkey '{hk_str}'")
                    continue
                ok = _user32.RegisterHotKey(None, next_id, mods | MOD_NOREPEAT, vk)
                if not ok:
                    err = _kernel32.GetLastError()
                    # err=1409 (ERROR_HOTKEY_ALREADY_REGISTERED) is the usual cause
                    print(f"[ERROR] RegisterHotKey failed for '{hk_str}' (err={err})")
                    continue
                self._id_to_binding[next_id] = (hk_str, cb)
                next_id += 1
            self._ready.set()

            msg = wintypes.MSG()
            while True:
                ret = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break  # WM_QUIT (0) or error (-1)
                if msg.message == WM_HOTKEY:
                    hk_id = int(msg.wParam)
                    binding = self._id_to_binding.get(hk_id)
                    if binding:
                        hk_str, cb = binding
                        self.activation_count += 1
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        print(f"\n[{ts}] 🔥 Hotkey activated! ({hk_str})")
                        if cb:
                            threading.Thread(target=cb, daemon=True).start()
                _user32.TranslateMessage(ctypes.byref(msg))
                _user32.DispatchMessageW(ctypes.byref(msg))

            for hk_id in list(self._id_to_binding.keys()):
                try:
                    _user32.UnregisterHotKey(None, hk_id)
                except Exception:
                    pass
            self._id_to_binding = {}

        def start(self):
            if self.running:
                print("[WARNING] Listener already running")
                return
            if not self.bindings:
                print("[WARNING] No hotkey bindings configured")
                return
            self._ready = threading.Event()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self._ready.wait(timeout=3.0)
            self.running = True
            print(f"[INFO] Keyboard listener started — {len(self._id_to_binding)} hotkey(s) via Win32")
            for hk_str in self.bindings:
                print(f"[INFO] Press {hk_str} to activate AI assistant")
            print("[INFO] Press Ctrl+C to stop")

        def stop(self):
            if not self.running:
                return
            if self._thread_id is not None:
                try:
                    _user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
                except Exception:
                    pass
            if self._thread is not None:
                self._thread.join(timeout=2.0)
            self._thread = None
            self._thread_id = None
            self.running = False
            print("[INFO] Keyboard listener stopped")
            print(f"[INFO] Total activations: {self.activation_count}")

        def wait(self):
            pass

        def change_hotkey(self, new_hotkey):
            was_running = self.running
            if was_running:
                self.stop()
            cb = list(self.bindings.values())[0] if self.bindings else None
            self.bindings = {new_hotkey: cb}
            self.hotkey = new_hotkey
            if was_running:
                self.start()
            print(f"[INFO] Hotkey changed to: {new_hotkey}")


# =============================================================================
# Public API: platform-specific class is exported as KeyboardListener
# =============================================================================

if _IS_MAC:
    KeyboardListener = _MacKeyboardListener
elif _IS_WIN:
    KeyboardListener = _WindowsKeyboardListener
else:
    class _UnsupportedKeyboardListener:
        """Stub for unsupported platforms — agent still runs, just no hotkeys."""

        def __init__(self, callback=None, hotkey='ctrl+alt+a', bindings=None):
            if bindings:
                self.bindings = dict(bindings)
            else:
                self.bindings = {hotkey: callback} if callback else {}
            self.hotkey = hotkey
            self.running = False
            self.activation_count = 0

        def set_callback(self, callback):
            self.bindings = {self.hotkey: callback}

        def start(self):
            print(f"[ERROR] Global hotkeys not supported on {sys.platform}; "
                  "the overlay's input field still works.")

        def stop(self):
            pass

        def wait(self):
            pass

        def change_hotkey(self, new_hotkey):
            self.hotkey = new_hotkey
            self.bindings = {new_hotkey: list(self.bindings.values())[0] if self.bindings else None}

    KeyboardListener = _UnsupportedKeyboardListener
