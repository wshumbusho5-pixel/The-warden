"""
Transparent overlay window for displaying AI responses
"""

import tkinter as tk
from tkinter import scrolledtext
import threading


class ResponseOverlay:
    """Creates a transparent overlay window to display AI responses"""

    def __init__(self):
        self.window = None
        self.text_widget = None
        self.is_visible = False

    def create_window(self):
        """Create the overlay window"""
        if self.window is not None:
            return

        # Create main window
        self.window = tk.Tk()
        self.window.title("AI Assistant")

        # Window configuration
        self.window.attributes('-topmost', True)  # Always on top
        self.window.attributes('-alpha', 0.95)     # Slightly transparent

        # On macOS, make it float above all windows
        try:
            self.window.attributes('-type', 'utility')  # macOS
        except:
            pass

        # Window size and position
        window_width = 500
        window_height = 400

        # Center on screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Style
        self.window.configure(bg='#1e1e1e')

        # Title label
        title_frame = tk.Frame(self.window, bg='#2d2d2d', height=40)
        title_frame.pack(fill=tk.X, padx=0, pady=0)

        title_label = tk.Label(
            title_frame,
            text="🤖 Invisible AI Assistant",
            bg='#2d2d2d',
            fg='#ffffff',
            font=('Arial', 12, 'bold'),
            pady=10
        )
        title_label.pack()

        # Text display area
        text_frame = tk.Frame(self.window, bg='#1e1e1e')
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.text_widget = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            bg='#2d2d2d',
            fg='#ffffff',
            font=('Arial', 11),
            insertbackground='white',
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)

        # Button frame
        button_frame = tk.Frame(self.window, bg='#1e1e1e')
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Close button
        close_btn = tk.Button(
            button_frame,
            text="Close (ESC)",
            command=self.hide,
            bg='#404040',
            fg='#ffffff',
            font=('Arial', 10),
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor='hand2'
        )
        close_btn.pack(side=tk.RIGHT)

        # Copy button
        copy_btn = tk.Button(
            button_frame,
            text="Copy",
            command=self.copy_to_clipboard,
            bg='#404040',
            fg='#ffffff',
            font=('Arial', 10),
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor='hand2'
        )
        copy_btn.pack(side=tk.RIGHT, padx=5)

        # Keyboard bindings
        self.window.bind('<Escape>', lambda e: self.hide())
        self.window.bind('<Control-c>', lambda e: self.copy_to_clipboard())

        # Don't show window yet
        self.window.withdraw()

    def show(self, content, metadata=None):
        """
        Show the overlay with content

        Args:
            content: Text to display
            metadata: Optional metadata dict with model, tokens, etc.
        """
        # Create window if it doesn't exist
        if self.window is None:
            self.create_window()

        # Clear previous content
        self.text_widget.delete(1.0, tk.END)

        # Insert new content
        self.text_widget.insert(1.0, content)

        # Add metadata if provided
        if metadata:
            self.text_widget.insert(tk.END, f"\n\n{'─'*50}\n")
            self.text_widget.insert(tk.END, f"Model: {metadata.get('model', 'unknown')}\n")
            self.text_widget.insert(tk.END, f"Tokens: {metadata.get('tokens_used', 'unknown')}\n")
            self.text_widget.insert(tk.END, f"Time: {metadata.get('timestamp', 'unknown')}\n")

        # Show window
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()
        self.is_visible = True

    def hide(self):
        """Hide the overlay"""
        if self.window:
            self.window.withdraw()
            self.is_visible = False

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
            self.window.destroy()
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
