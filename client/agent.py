#!/usr/bin/env python3
"""
Invisible AI Assistant - Client Agent
Runs invisibly in the background and captures context for AI processing
"""

import asyncio
import websockets
import json
import pyperclip
import pyautogui
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class InvisibleAgent:
    """Lightweight client that runs on user devices"""

    def __init__(self, server_ip=None, server_port=8765):
        self.server_ip = server_ip or os.getenv("MAIN_COMPUTER_IP", "localhost")
        self.server_port = server_port
        self.server_url = f"ws://{self.server_ip}:{self.server_port}"
        self.ws = None
        print(f"[{self._timestamp()}] Agent initialized - Server: {self.server_url}")

    def _timestamp(self):
        """Generate timestamp for logging"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def capture_context(self, question=""):
        """Capture current screen context"""
        try:
            # Get clipboard content
            clipboard_content = pyperclip.paste()

            # For MVP, we'll skip screen capture and OCR to avoid complexity
            # This can be added in Phase 2
            context = {
                'clipboard': clipboard_content,
                'screen_text': '',  # Will implement OCR in Phase 2
                'question': question,
                'timestamp': self._timestamp()
            }

            return context

        except Exception as e:
            print(f"[{self._timestamp()}] Error capturing context: {e}")
            return {
                'clipboard': '',
                'screen_text': '',
                'question': question,
                'timestamp': self._timestamp()
            }

    async def send_request(self, question=""):
        """Send request to server and get response"""
        try:
            print(f"\n[{self._timestamp()}] Connecting to server...")

            async with websockets.connect(self.server_url) as websocket:
                print(f"[{self._timestamp()}] Connected!")

                # Capture context
                context = self.capture_context(question)

                # Build request
                request = {
                    'type': 'question',
                    'context': context
                }

                print(f"[{self._timestamp()}] Sending request...")
                # Send to server
                await websocket.send(json.dumps(request))

                # Wait for response
                print(f"[{self._timestamp()}] Waiting for AI response...")
                response = await websocket.recv()
                response_data = json.loads(response)

                # Display response
                self.display_response(response_data)

                return response_data

        except websockets.exceptions.WebSocketException as e:
            print(f"[{self._timestamp()}] Connection error: {e}")
            print(f"[{self._timestamp()}] Make sure the server is running at {self.server_url}")
        except Exception as e:
            print(f"[{self._timestamp()}] Error: {e}")

    def display_response(self, response):
        """Display AI response"""
        print(f"\n{'='*60}")
        print(f"  AI Response")
        print(f"{'='*60}\n")

        if response.get('type') == 'error':
            print(f"ERROR: {response.get('content')}")
        else:
            content = response.get('content', 'No response')
            print(content)

            # Show metadata if available
            metadata = response.get('metadata', {})
            if metadata:
                print(f"\n{'-'*60}")
                print(f"Model: {metadata.get('model', 'unknown')}")
                print(f"Tokens: {metadata.get('tokens_used', 'unknown')}")
                print(f"Time: {metadata.get('timestamp', 'unknown')}")

        print(f"\n{'='*60}\n")

    async def interactive_mode(self):
        """Run in interactive mode for testing"""
        print(f"\n{'='*60}")
        print(f"  Invisible AI Assistant - Client")
        print(f"{'='*60}")
        print(f"  Server: {self.server_url}")
        print(f"  Time: {self._timestamp()}")
        print(f"{'='*60}\n")
        print("Type your questions (or 'quit' to exit):\n")

        while True:
            try:
                question = input("You: ").strip()

                if question.lower() in ['quit', 'exit', 'q']:
                    print(f"[{self._timestamp()}] Goodbye!")
                    break

                if not question:
                    continue

                await self.send_request(question)

            except KeyboardInterrupt:
                print(f"\n[{self._timestamp()}] Interrupted by user")
                break
            except Exception as e:
                print(f"[{self._timestamp()}] Error: {e}")


def main():
    """Main entry point"""
    import sys

    # Get server IP from command line or use default
    server_ip = sys.argv[1] if len(sys.argv) > 1 else None

    agent = InvisibleAgent(server_ip=server_ip)

    # Run in interactive mode for testing
    asyncio.run(agent.interactive_mode())


if __name__ == "__main__":
    main()
