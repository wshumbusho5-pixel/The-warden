"""
Global hotkey listener using Carbon's RegisterEventHotKey on macOS.

Why Carbon and not pynput?
  pynput uses CGEventTap, which intercepts every keystroke globally and so
  requires Accessibility permission. macOS grants that per code-signing
  hash, which breaks for ad-hoc-signed PyInstaller bundles every time you
  rebuild.

  Carbon's RegisterEventHotKey just tells the OS "call me when this exact
  combo fires." It can't see other keys, so it doesn't need Accessibility.
  This is what every native macOS app uses for global shortcuts.
"""

import ctypes
import ctypes.util
import threading
from datetime import datetime


def _fourcc(s):
    return (ord(s[0]) << 24) | (ord(s[1]) << 16) | (ord(s[2]) << 8) | ord(s[3])


# --- Carbon constants -----------------------------------------------------

CMD_KEY     = 1 << 8       # 256
SHIFT_KEY   = 1 << 9       # 512
OPTION_KEY  = 1 << 11      # 2048
CONTROL_KEY = 1 << 12      # 4096

K_EVENT_CLASS_KEYBOARD   = _fourcc('keyb')
K_EVENT_HOTKEY_PRESSED   = 5
K_EVENT_PARAM_DIRECT_OBJ = _fourcc('----')
TYPE_EVENT_HOTKEY_ID     = _fourcc('hkid')

MODIFIER_MAP = {
    'cmd': CMD_KEY, 'command': CMD_KEY, 'super': CMD_KEY, 'win': CMD_KEY,
    'shift': SHIFT_KEY,
    'option': OPTION_KEY, 'opt': OPTION_KEY, 'alt': OPTION_KEY,
    'ctrl': CONTROL_KEY, 'control': CONTROL_KEY,
}

# macOS virtual key codes (kVK_ANSI_*)
KEY_CODES = {
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


# --- Carbon function bindings --------------------------------------------

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


def _parse_hotkey(hotkey_str):
    """'ctrl+alt+a' -> (modifier_flags, key_code). Returns (None, None) on parse error."""
    parts = [p.strip().lower() for p in hotkey_str.split('+')]
    mods = 0
    key_code = None
    for p in parts:
        if p in MODIFIER_MAP:
            mods |= MODIFIER_MAP[p]
        elif p in KEY_CODES:
            key_code = KEY_CODES[p]
        else:
            return None, None
    if key_code is None:
        return None, None
    return mods, key_code


class KeyboardListener:
    """Global hotkey listener using Carbon. No Accessibility permission needed."""

    SIGNATURE = _fourcc('TxKt')  # arbitrary 4-char sig identifying our hotkeys

    def __init__(self, callback=None, hotkey='ctrl+alt+a', bindings=None):
        if bindings:
            self.bindings = dict(bindings)
        else:
            self.bindings = {hotkey: callback} if callback else {}
        self.hotkey = hotkey  # legacy display
        self.running = False
        self.activation_count = 0
        self._handler_ref = None
        self._handler_cb = None  # keep CFUNCTYPE alive
        self._hk_refs = []
        self._id_to_binding = {}  # id -> (hotkey_str, callback)

    # legacy single-callback setter
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

        # Install one event handler for hotkey-pressed events
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

        # Register each hotkey
        next_id = 1
        for hk_str, cb in self.bindings.items():
            print(f"[INFO] Registering hotkey: {hk_str}")
            mods, key_code = _parse_hotkey(hk_str)
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
        # Carbon events fire from the main thread's run loop. The Tk mainloop
        # in invisible_agent.start_background_mode keeps the run loop alive,
        # so this method (kept for backward compat) doesn't need to block.
        pass

    def change_hotkey(self, new_hotkey):
        was_running = self.running
        if was_running:
            self.stop()
        self.bindings = {new_hotkey: list(self.bindings.values())[0] if self.bindings else None}
        self.hotkey = new_hotkey
        if was_running:
            self.start()
        print(f"[INFO] Hotkey changed to: {new_hotkey}")
