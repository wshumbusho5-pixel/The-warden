"""
Keyboard shortcut listener for invisible activation
"""

import threading
from datetime import datetime
from pynput import keyboard as pk


def _to_pynput_hotkey(hotkey):
    """Translate 'f1' -> '<f1>', 'ctrl+shift+a' -> '<ctrl>+<shift>+a' for pynput."""
    parts = [p.strip().lower() for p in hotkey.split('+')]
    out = []
    for p in parts:
        if len(p) > 1:
            out.append(f"<{p}>")
        else:
            out.append(p)
    return '+'.join(out)


class KeyboardListener:
    """Listens for keyboard shortcuts to trigger AI assistant"""

    def __init__(self, callback=None, hotkey='f1'):
        self.callback = callback
        self.hotkey = hotkey
        self.running = False
        self.activation_count = 0
        self._listener = None

    def set_callback(self, callback):
        self.callback = callback

    def on_hotkey_triggered(self):
        self.activation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n[{timestamp}] 🔥 Hotkey activated! ({self.hotkey})")

        if self.callback:
            try:
                thread = threading.Thread(target=self.callback)
                thread.daemon = True
                thread.start()
            except Exception as e:
                print(f"[ERROR] Callback failed: {e}")
        else:
            print("[WARNING] No callback set for hotkey")

    def start(self):
        if self.running:
            print("[WARNING] Listener already running")
            return

        try:
            print(f"[INFO] Registering hotkey: {self.hotkey}")
            mapping = {_to_pynput_hotkey(self.hotkey): self.on_hotkey_triggered}
            self._listener = pk.GlobalHotKeys(mapping)
            self._listener.start()
            self.running = True
            print(f"[INFO] Keyboard listener started")
            print(f"[INFO] Press {self.hotkey} to activate AI assistant")
            print(f"[INFO] Press Ctrl+C to stop")
        except Exception as e:
            print(f"[ERROR] Failed to start keyboard listener: {e}")
            print(f"[INFO] On macOS, grant Accessibility permission to your terminal:")
            print(f"       System Settings → Privacy & Security → Accessibility")

    def stop(self):
        if not self.running:
            return

        try:
            if self._listener is not None:
                self._listener.stop()
                self._listener = None
            self.running = False
            print(f"[INFO] Keyboard listener stopped")
            print(f"[INFO] Total activations: {self.activation_count}")
        except Exception as e:
            print(f"[ERROR] Failed to stop keyboard listener: {e}")

    def wait(self):
        if not self.running:
            print("[WARNING] Listener not running. Call start() first.")
            return

        try:
            print(f"\n{'='*60}")
            print(f"  Invisible AI Assistant - Active")
            print(f"{'='*60}")
            print(f"  Hotkey: {self.hotkey}")
            print(f"  Status: Listening...")
            print(f"{'='*60}\n")

            self._listener.join()  # Block until listener stops
        except KeyboardInterrupt:
            print(f"\n[INFO] Interrupted by user")
            self.stop()

    def change_hotkey(self, new_hotkey):
        was_running = self.running

        if was_running:
            self.stop()

        self.hotkey = new_hotkey

        if was_running:
            self.start()

        print(f"[INFO] Hotkey changed to: {new_hotkey}")


def test_callback():
    print("🎉 Test callback executed!")


if __name__ == "__main__":
    print("Testing keyboard listener...")
    print("Press F1 to test")
    print("Press Ctrl+C to exit")

    listener = KeyboardListener(callback=test_callback)
    listener.start()
    listener.wait()
