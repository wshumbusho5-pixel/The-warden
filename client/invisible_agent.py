#!/usr/bin/env python3
"""
Invisible AI Assistant - Enhanced Client Agent
Full featured agent with screen capture, OCR, keyboard shortcuts, and overlay display
"""

import asyncio
import websockets
import json
import pyperclip
from datetime import datetime
import os
import sys
from dotenv import load_dotenv

# Import our modules
from screen_capture import ScreenCapture
from keyboard_listener import KeyboardListener
from overlay_display import ResponseOverlay

# Load environment variables
load_dotenv()


class InvisibleAgentPro:
    """
    Enhanced Invisible Agent with full features:
    - Screen capture + OCR
    - Keyboard shortcuts
    - Transparent overlay
    - Background operation
    """

    def __init__(self, server_ip=None, server_port=8765):
        self.server_ip = server_ip or os.getenv("MAIN_COMPUTER_IP", "localhost")
        self.server_port = server_port
        self.server_url = f"ws://{self.server_ip}:{self.server_port}"

        # Initialize components
        self.screen_capture = ScreenCapture()
        self.keyboard_listener = KeyboardListener(
            callback=self.on_hotkey_activated,
            hotkey='f1'
        )
        self.overlay = ResponseOverlay()

        # State
        self.running = False
        self.request_count = 0

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
            'screen_text': ''
        }

        try:
            # Capture clipboard
            clipboard_content = pyperclip.paste()
            if clipboard_content:
                context['clipboard'] = clipboard_content[:1000]  # Limit size

            # Capture screen if enabled
            if use_screen:
                print(f"[{self._timestamp()}] Capturing screen...")
                screen_text = self.screen_capture.capture_and_extract()
                if screen_text:
                    # Limit to 2000 characters to avoid huge payloads
                    context['screen_text'] = screen_text[:2000]
                    print(f"[{self._timestamp()}] Captured {len(screen_text)} characters from screen")

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

        try:
            print(f"[{self._timestamp()}] Connecting to server...")

            async with websockets.connect(self.server_url) as websocket:
                print(f"[{self._timestamp()}] Connected!")

                # Capture context
                context = self.capture_context(question, use_screen)

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

                return response_data

        except websockets.exceptions.WebSocketException as e:
            print(f"[{self._timestamp()}] Connection error: {e}")
            return {
                'type': 'error',
                'content': f'Could not connect to server at {self.server_url}\nMake sure the server is running.',
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

        # Show in overlay
        self.overlay.show(content, metadata)

    def on_hotkey_activated(self):
        """Called when user presses the hotkey"""
        print(f"\n{'='*60}")
        print(f"  🔥 AI ASSISTANT ACTIVATED")
        print(f"{'='*60}\n")

        # Run async request in event loop
        try:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Send request (with screen capture)
            response = loop.run_until_complete(
                self.send_request(question="Help me with what's on my screen", use_screen=True)
            )

            # Display response
            self.display_response(response)

        except Exception as e:
            print(f"[{self._timestamp()}] Error handling hotkey: {e}")
        finally:
            loop.close()

    def start_background_mode(self):
        """
        Start in background mode - listens for hotkey and responds invisibly
        """
        print(f"\n{'='*60}")
        print(f"  Invisible AI Assistant - Background Mode")
        print(f"{'='*60}")
        print(f"  Server: {self.server_url}")
        print(f"  Hotkey: F1")
        print(f"  Status: Running invisibly...")
        print(f"{'='*60}\n")
        print(f"[{self._timestamp()}] Press F1 to activate AI")
        print(f"[{self._timestamp()}] Press Ctrl+C to stop\n")

        self.running = True

        # Start keyboard listener
        self.keyboard_listener.start()

        # Wait for keyboard events
        try:
            self.keyboard_listener.wait()
        except KeyboardInterrupt:
            print(f"\n[{self._timestamp()}] Stopping...")
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


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Invisible AI Assistant Client')
    parser.add_argument('server_ip', nargs='?', help='Server IP address (optional)')
    parser.add_argument('--mode', choices=['background', 'interactive'],
                        default='background',
                        help='Run mode (default: background)')
    parser.add_argument('--port', type=int, default=8765,
                        help='Server port (default: 8765)')

    args = parser.parse_args()

    # Create agent
    agent = InvisibleAgentPro(server_ip=args.server_ip, server_port=args.port)

    # Run in selected mode
    if args.mode == 'background':
        agent.start_background_mode()
    else:
        asyncio.run(agent.interactive_mode())


if __name__ == "__main__":
    main()
