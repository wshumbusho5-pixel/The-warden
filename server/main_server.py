#!/usr/bin/env python3
"""
Invisible AI Assistant - Main Server
Handles all AI processing and serves multiple client devices
"""

import asyncio
import websockets
import json
import os
import re
import threading
from dotenv import load_dotenv
from datetime import datetime
from server_display import ServerDisplay
from ai_providers import AIProviderFactory

# Load environment variables
load_dotenv()


class InvisibleAIServer:
    """Main brain of the Invisible AI system"""

    def __init__(self, enable_server_display=True, ai_provider=None):
        # Initialize AI provider
        if ai_provider:
            # Use specified provider
            self.ai_provider = ai_provider
        else:
            # Auto-detect available provider
            print(f"[{self._timestamp()}] Auto-detecting AI provider...")
            self.ai_provider = AIProviderFactory.auto_detect()

            if not self.ai_provider:
                print("\n" + "="*60)
                print("❌ NO AI PROVIDER FOUND!")
                print("="*60)
                print("\nOptions:")
                print("1. Install Ollama (FREE, local):")
                print("   → https://ollama.ai")
                print("   → Run: ollama pull llama3.2")
                print("")
                print("2. Add Claude API key to .env:")
                print("   → ANTHROPIC_API_KEY=your-key")
                print("")
                print("3. Add OpenAI API key to .env:")
                print("   → OPENAI_API_KEY=your-key")
                print("="*60 + "\n")
                raise ValueError("No AI provider available. See options above.")

        self.connected_clients = set()

        # Initialize server display. Tk requires its window be created on the
        # main thread on macOS, so we build it here (main() runs us on the main
        # thread) and main() will drive mainloop while asyncio runs on a worker.
        self.server_display = None
        if enable_server_display:
            self.server_display = ServerDisplay()
            self.server_display.create_window()

        print(f"[{self._timestamp()}] Invisible AI Server initialized")
        print(f"[{self._timestamp()}] AI Provider: {self.ai_provider.name}")
        if hasattr(self.ai_provider, 'model'):
            print(f"[{self._timestamp()}] Model: {self.ai_provider.model}")

    def _timestamp(self):
        """Generate timestamp for logging"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _parse_display_mode(self, question):
        """
        Parse display mode from question

        Supports:
        /server - show only on server
        /client - show only on client (default)
        /both - show on both
        /silent - show nowhere (for privacy)

        Returns:
            tuple: (cleaned_question, display_mode)
        """
        display_mode = 'client'  # Default

        if not question:
            return question, display_mode

        # Check for modifiers
        if '/server' in question.lower():
            display_mode = 'server'
            question = re.sub(r'/server\s*', '', question, flags=re.IGNORECASE)
        elif '/both' in question.lower():
            display_mode = 'both'
            question = re.sub(r'/both\s*', '', question, flags=re.IGNORECASE)
        elif '/silent' in question.lower():
            display_mode = 'silent'
            question = re.sub(r'/silent\s*', '', question, flags=re.IGNORECASE)
        elif '/client' in question.lower():
            display_mode = 'client'
            question = re.sub(r'/client\s*', '', question, flags=re.IGNORECASE)

        return question.strip(), display_mode

    async def handle_client(self, websocket, path):
        """Handle incoming client connections"""
        # Register client
        self.connected_clients.add(websocket)
        client_id = id(websocket)
        print(f"[{self._timestamp()}] Client {client_id} connected. Total clients: {len(self.connected_clients)}")

        try:
            async for message in websocket:
                try:
                    # Parse request
                    data = json.loads(message)
                    print(f"[{self._timestamp()}] Received request from client {client_id}")

                    # Process and get AI response
                    response = await self.process_request(data, client_id)

                    # Send back to client
                    await websocket.send(json.dumps(response))
                    print(f"[{self._timestamp()}] Sent response to client {client_id}")

                except json.JSONDecodeError as e:
                    error_response = {
                        'type': 'error',
                        'content': f'Invalid JSON: {str(e)}',
                        'timestamp': self._timestamp()
                    }
                    await websocket.send(json.dumps(error_response))

                except Exception as e:
                    error_response = {
                        'type': 'error',
                        'content': f'Processing error: {str(e)}',
                        'timestamp': self._timestamp()
                    }
                    await websocket.send(json.dumps(error_response))
                    print(f"[{self._timestamp()}] Error processing request: {e}")

        except websockets.exceptions.ConnectionClosed:
            print(f"[{self._timestamp()}] Client {client_id} disconnected")
        finally:
            self.connected_clients.remove(websocket)
            print(f"[{self._timestamp()}] Total clients: {len(self.connected_clients)}")

    async def process_request(self, request, client_id=None):
        """Process client request and generate AI response"""
        context = request.get('context', {})
        screen_text = context.get('screen_text', '')
        clipboard = context.get('clipboard', '')
        question = context.get('question', '')

        # Parse display mode from question
        question, display_mode = self._parse_display_mode(question)

        # Build AI prompt based on context
        prompt_parts = []

        if question:
            prompt_parts.append(f"User question: {question}")

        if screen_text:
            prompt_parts.append(f"\nScreen content:\n{screen_text[:1000]}")  # Limit to 1000 chars

        if clipboard:
            prompt_parts.append(f"\nClipboard: {clipboard[:500]}")  # Limit to 500 chars

        if not prompt_parts:
            prompt = "Hello! I'm ready to assist you. What can I help you with?"
        else:
            prompt = "\n".join(prompt_parts)
            prompt += "\n\nProvide helpful assistance based on this context. Be concise and actionable."

        print(f"[{self._timestamp()}] Display mode: {display_mode}")
        print(f"[{self._timestamp()}] Sending request to {self.ai_provider.name}...")

        # Call AI provider
        try:
            result = self.ai_provider.generate(prompt, max_tokens=2000)

            if result['success']:
                response_text = result['content']

                metadata = {
                    'model': result.get('model', 'unknown'),
                    'provider': result.get('provider', 'unknown'),
                    'tokens_used': result.get('tokens_used', 0),
                    'timestamp': self._timestamp()
                }

                # Show on server display if needed
                if self.server_display and display_mode in ['server', 'both']:
                    self.server_display.append_response(
                        response_text,
                        metadata=metadata,
                        client_id=client_id
                    )

                return {
                    'type': 'response',
                    'content': response_text,
                    'metadata': metadata,
                    'display_mode': display_mode  # Tell client where to show
                }
            else:
                # AI provider returned error
                error_msg = result.get('error', 'Unknown error')
                print(f"[{self._timestamp()}] AI provider error: {error_msg}")
                return {
                    'type': 'error',
                    'content': f'AI service error: {error_msg}',
                    'timestamp': self._timestamp(),
                    'display_mode': display_mode
                }

        except Exception as e:
            print(f"[{self._timestamp()}] AI provider error: {e}")
            return {
                'type': 'error',
                'content': f'AI service error: {str(e)}',
                'timestamp': self._timestamp(),
                'display_mode': display_mode
            }

    async def start_server(self, host="0.0.0.0", port=8765):
        """Start the WebSocket server"""
        print(f"\n{'='*60}")
        print(f"  Invisible AI Assistant - Server Starting")
        print(f"{'='*60}")
        print(f"  Host: {host}")
        print(f"  Port: {port}")
        print(f"  AI Provider: {self.ai_provider.name}")
        if hasattr(self.ai_provider, 'model'):
            print(f"  Model: {self.ai_provider.model}")
        print(f"  Time: {self._timestamp()}")
        print(f"{'='*60}\n")

        async with websockets.serve(self.handle_client, host, port):
            print(f"[{self._timestamp()}] Server is running and waiting for clients...")
            print(f"[{self._timestamp()}] Press Ctrl+C to stop\n")
            await asyncio.Future()  # Run forever


def main():
    """Main entry point"""
    try:
        server = InvisibleAIServer()

        if server.server_display is not None:
            # Tk owns the main thread; run asyncio in a daemon worker.
            def _run_asyncio():
                try:
                    asyncio.run(server.start_server())
                except Exception as e:
                    print(f"[asyncio] {e}")

            threading.Thread(target=_run_asyncio, daemon=True).start()
            server.server_display.run()  # blocks on Tk mainloop
        else:
            asyncio.run(server.start_server())
    except KeyboardInterrupt:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Server stopped by user")
    except Exception as e:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Server error: {e}")
        raise


if __name__ == "__main__":
    main()
