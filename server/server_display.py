"""
Server-side response display
Shows AI responses on the main computer
"""

import tkinter as tk
from tkinter import scrolledtext
import threading


class ServerDisplay:
    """Display AI responses on the server/main computer"""

    def __init__(self):
        self.window = None
        self.text_widget = None
        self.is_visible = False
        self.response_count = 0

    def create_window(self):
        """Create the display window"""
        if self.window is not None:
            return

        # Create main window
        self.window = tk.Tk()
        self.window.title("AI Server - Responses")

        # Window configuration
        self.window.attributes('-topmost', True)  # Always on top

        # Window size and position
        window_width = 600
        window_height = 500

        # Position on right side of screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = screen_width - window_width - 20
        y = 50

        self.window.geometry(f"{window_width}x{window_height}+{x}+{y}")

        # Style
        self.window.configure(bg='#1a1a1a')

        # Title bar
        title_frame = tk.Frame(self.window, bg='#2d2d30', height=50)
        title_frame.pack(fill=tk.X, padx=0, pady=0)

        title_label = tk.Label(
            title_frame,
            text="🖥️ Server Display - AI Responses",
            bg='#2d2d30',
            fg='#ffffff',
            font=('Arial', 13, 'bold'),
            pady=12
        )
        title_label.pack()

        # Stats frame
        stats_frame = tk.Frame(self.window, bg='#1a1a1a')
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        self.stats_label = tk.Label(
            stats_frame,
            text=f"Responses: 0",
            bg='#1a1a1a',
            fg='#888888',
            font=('Arial', 9),
            anchor=tk.W
        )
        self.stats_label.pack(side=tk.LEFT)

        # Text display area
        text_frame = tk.Frame(self.window, bg='#1a1a1a')
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.text_widget = scrolledtext.ScrolledText(
            text_frame,
            wrap=tk.WORD,
            bg='#252526',
            fg='#cccccc',
            font=('Consolas', 10),
            insertbackground='white',
            relief=tk.FLAT,
            padx=15,
            pady=15
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)

        # Configure tags for styling
        self.text_widget.tag_config('header', foreground='#4ec9b0', font=('Arial', 11, 'bold'))
        self.text_widget.tag_config('metadata', foreground='#888888', font=('Arial', 9))
        self.text_widget.tag_config('separator', foreground='#444444')

        # Button frame
        button_frame = tk.Frame(self.window, bg='#1a1a1a')
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Clear button
        clear_btn = tk.Button(
            button_frame,
            text="Clear",
            command=self.clear,
            bg='#3e3e42',
            fg='#ffffff',
            font=('Arial', 10),
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor='hand2'
        )
        clear_btn.pack(side=tk.LEFT, padx=5)

        # Copy button
        copy_btn = tk.Button(
            button_frame,
            text="Copy Last",
            command=self.copy_to_clipboard,
            bg='#3e3e42',
            fg='#ffffff',
            font=('Arial', 10),
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor='hand2'
        )
        copy_btn.pack(side=tk.LEFT, padx=5)

        # Minimize button
        minimize_btn = tk.Button(
            button_frame,
            text="Minimize",
            command=self.minimize,
            bg='#3e3e42',
            fg='#ffffff',
            font=('Arial', 10),
            relief=tk.FLAT,
            padx=15,
            pady=6,
            cursor='hand2'
        )
        minimize_btn.pack(side=tk.RIGHT, padx=5)

        # Keyboard bindings
        self.window.bind('<Control-l>', lambda e: self.clear())
        self.window.bind('<Control-c>', lambda e: self.copy_to_clipboard())

        # Show welcome message
        self.show_welcome()

    def show_welcome(self):
        """Show welcome message"""
        welcome = """Server Display Ready

Responses will appear here when display mode is set to 'server' or 'both'.

Press F1 on any connected client to activate AI.

"""
        self.text_widget.insert(1.0, welcome, 'metadata')

    def append_response(self, content, metadata=None, client_id=None):
        """
        Append a new response to the display

        Args:
            content: Response text
            metadata: Optional metadata dict
            client_id: ID of client that sent request
        """
        self.response_count += 1

        # Update stats
        self.stats_label.config(text=f"Responses: {self.response_count}")

        # Add separator
        if self.response_count > 1:
            self.text_widget.insert(tk.END, "\n" + "━" * 80 + "\n\n", 'separator')

        # Add header
        header = f"Response #{self.response_count}"
        if client_id:
            header += f" (Client: {client_id})"
        header += "\n"
        self.text_widget.insert(tk.END, header, 'header')

        # Add content
        self.text_widget.insert(tk.END, content + "\n")

        # Add metadata
        if metadata:
            meta_text = f"\nModel: {metadata.get('model', 'unknown')} | "
            meta_text += f"Tokens: {metadata.get('tokens_used', 'unknown')} | "
            meta_text += f"Time: {metadata.get('timestamp', 'unknown')}\n"
            self.text_widget.insert(tk.END, meta_text, 'metadata')

        # Auto-scroll to bottom
        self.text_widget.see(tk.END)

        # Show window if hidden
        if not self.is_visible:
            self.show()

    def show(self):
        """Show the window"""
        if self.window is None:
            self.create_window()

        self.window.deiconify()
        self.window.lift()
        self.is_visible = True

    def minimize(self):
        """Minimize the window"""
        if self.window:
            self.window.iconify()
            self.is_visible = False

    def clear(self):
        """Clear all responses"""
        if self.text_widget:
            self.text_widget.delete(1.0, tk.END)
            self.response_count = 0
            self.stats_label.config(text=f"Responses: 0")
            self.show_welcome()

    def copy_to_clipboard(self):
        """Copy all content to clipboard"""
        if self.text_widget:
            content = self.text_widget.get(1.0, tk.END)
            self.window.clipboard_clear()
            self.window.clipboard_append(content)
            print("[INFO] Content copied to clipboard")

    def run(self):
        """Run the display window (blocking)"""
        if self.window is None:
            self.create_window()
        self.window.mainloop()

    def run_in_thread(self):
        """Run the display in a separate thread"""
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        return thread


# Test
if __name__ == "__main__":
    display = ServerDisplay()

    # Test with sample responses
    display.append_response(
        "This is a test response from the AI assistant.",
        metadata={
            'model': 'claude-sonnet-4',
            'tokens_used': 150,
            'timestamp': '2025-12-22 23:30:00'
        },
        client_id="test-123"
    )

    display.run()
