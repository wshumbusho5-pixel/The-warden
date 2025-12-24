"""
Keyboard shortcut listener for invisible activation
"""

import keyboard
import threading
from datetime import datetime


class KeyboardListener:
    """Listens for keyboard shortcuts to trigger AI assistant"""

    def __init__(self, callback=None, hotkey='f1'):
        """
        Initialize keyboard listener

        Args:
            callback: Function to call when hotkey is pressed
            hotkey: Keyboard shortcut (default: f1)
        """
        self.callback = callback
        self.hotkey = hotkey
        self.running = False
        self.activation_count = 0

    def set_callback(self, callback):
        """Set the callback function"""
        self.callback = callback

    def on_hotkey_triggered(self):
        """Called when hotkey is pressed"""
        self.activation_count += 1
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n[{timestamp}] 🔥 Hotkey activated! ({self.hotkey})")

        if self.callback:
            try:
                # Run callback in separate thread to avoid blocking
                thread = threading.Thread(target=self.callback)
                thread.daemon = True
                thread.start()
            except Exception as e:
                print(f"[ERROR] Callback failed: {e}")
        else:
            print("[WARNING] No callback set for hotkey")

    def start(self):
        """Start listening for keyboard shortcuts"""
        if self.running:
            print("[WARNING] Listener already running")
            return

        try:
            print(f"[INFO] Registering hotkey: {self.hotkey}")
            keyboard.add_hotkey(self.hotkey, self.on_hotkey_triggered)
            self.running = True
            print(f"[INFO] Keyboard listener started")
            print(f"[INFO] Press {self.hotkey} to activate AI assistant")
            print(f"[INFO] Press Ctrl+C to stop")
        except Exception as e:
            print(f"[ERROR] Failed to start keyboard listener: {e}")
            print(f"[INFO] Note: Keyboard monitoring may require elevated permissions")

    def stop(self):
        """Stop listening for keyboard shortcuts"""
        if not self.running:
            return

        try:
            keyboard.remove_hotkey(self.hotkey)
            self.running = False
            print(f"[INFO] Keyboard listener stopped")
            print(f"[INFO] Total activations: {self.activation_count}")
        except Exception as e:
            print(f"[ERROR] Failed to stop keyboard listener: {e}")

    def wait(self):
        """Block and wait for keyboard events"""
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

            keyboard.wait()  # Block until interrupted
        except KeyboardInterrupt:
            print(f"\n[INFO] Interrupted by user")
            self.stop()

    def change_hotkey(self, new_hotkey):
        """
        Change the hotkey while running

        Args:
            new_hotkey: New keyboard shortcut string
        """
        was_running = self.running

        if was_running:
            self.stop()

        self.hotkey = new_hotkey

        if was_running:
            self.start()

        print(f"[INFO] Hotkey changed to: {new_hotkey}")


# Test function
def test_callback():
    """Test callback function"""
    print("🎉 Test callback executed!")


if __name__ == "__main__":
    # Test the keyboard listener
    print("Testing keyboard listener...")
    print("Press F1 to test")
    print("Press Ctrl+C to exit")

    listener = KeyboardListener(callback=test_callback)
    listener.start()
    listener.wait()
