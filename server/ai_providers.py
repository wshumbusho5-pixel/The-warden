"""
AI Provider Abstraction Layer
Supports: Claude (Anthropic), OpenAI (ChatGPT), Ollama (Local)
"""

import os
import requests
from anthropic import Anthropic
import openai
from datetime import datetime


class AIProvider:
    """Base class for AI providers"""

    def __init__(self):
        self.name = "Base Provider"

    def generate(self, prompt, max_tokens=2000):
        """Generate AI response - override in subclasses"""
        raise NotImplementedError

    def is_available(self):
        """Check if provider is available"""
        raise NotImplementedError


class ClaudeProvider(AIProvider):
    """Anthropic Claude AI Provider"""

    def __init__(self, api_key=None, model="claude-sonnet-4-6"):
        super().__init__()
        self.name = "Claude (Anthropic)"
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        # Bump default timeout (default ~60s can be too short on slow links).
        self.client = Anthropic(api_key=self.api_key, timeout=120.0, max_retries=2)

    def is_available(self):
        """Check if Claude is available"""
        return self.api_key is not None

    def generate(self, prompt, max_tokens=2000, system=None, history=None):
        """Generate response using Claude. `history` is a list of prior
        {role, content} message dicts; the new `prompt` is appended as the
        final user message."""
        try:
            messages = list(history) if history else []
            messages.append({"role": "user", "content": prompt})
            kwargs = dict(
                model=self.model,
                max_tokens=max_tokens,
                messages=messages,
            )
            if system:
                kwargs["system"] = system
            message = self.client.messages.create(**kwargs)

            return {
                'success': True,
                'content': message.content[0].text,
                'model': self.model,
                'provider': 'claude',
                'tokens_used': message.usage.input_tokens + message.usage.output_tokens
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider': 'claude'
            }


class OpenAIProvider(AIProvider):
    """OpenAI ChatGPT Provider"""

    def __init__(self, api_key=None, model="gpt-4"):
        super().__init__()
        self.name = "OpenAI (ChatGPT)"
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found")

        openai.api_key = self.api_key

    def is_available(self):
        """Check if OpenAI is available"""
        return self.api_key is not None

    def generate(self, prompt, max_tokens=2000, system=None, history=None):
        """Generate response using OpenAI"""
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            if history:
                messages.extend(history)
            messages.append({"role": "user", "content": prompt})
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens
            )

            return {
                'success': True,
                'content': response.choices[0].message.content,
                'model': self.model,
                'provider': 'openai',
                'tokens_used': response.usage.total_tokens
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider': 'openai'
            }


class OllamaProvider(AIProvider):
    """Ollama Local LLM Provider - FREE, NO API KEY NEEDED!"""

    def __init__(self, model="llama3.2", host="http://localhost:11434"):
        super().__init__()
        self.name = "Ollama (Local)"
        self.model = model
        self.host = host
        self.api_url = f"{host}/api/generate"

    def is_available(self):
        """Check if Ollama is running"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False

    def list_models(self):
        """List available Ollama models"""
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except:
            return []

    def generate(self, prompt, max_tokens=2000, system=None, history=None):
        """Generate response using Ollama. (history is currently flattened
        into the prompt — Ollama's /api/generate doesn't take messages.)"""
        if history:
            prefix = "\n\n".join(
                f"{m['role'].capitalize()}: {m['content']}" for m in history
            )
            prompt = f"{prefix}\n\nUser: {prompt}\n\nAssistant:"
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.7
                }
            }
            if system:
                payload["system"] = system

            response = requests.post(
                self.api_url,
                json=payload,
                timeout=60  # Ollama can be slow on first run
            )

            if response.status_code == 200:
                data = response.json()
                return {
                    'success': True,
                    'content': data.get('response', ''),
                    'model': self.model,
                    'provider': 'ollama',
                    'tokens_used': data.get('eval_count', 0)  # Approximate
                }
            else:
                return {
                    'success': False,
                    'error': f'Ollama API error: {response.status_code}',
                    'provider': 'ollama'
                }

        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'error': 'Ollama not running. Start with: ollama serve',
                'provider': 'ollama'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'provider': 'ollama'
            }


class AIProviderFactory:
    """Factory to create and manage AI providers"""

    @staticmethod
    def create_provider(provider_type, **kwargs):
        """
        Create an AI provider

        Args:
            provider_type: 'claude', 'openai', or 'ollama'
            **kwargs: Provider-specific arguments

        Returns:
            AIProvider instance
        """
        provider_type = provider_type.lower()

        if provider_type == 'claude':
            return ClaudeProvider(
                api_key=kwargs.get('api_key'),
                model=kwargs.get('model', 'claude-sonnet-4-6')
            )

        elif provider_type == 'openai':
            return OpenAIProvider(
                api_key=kwargs.get('api_key'),
                model=kwargs.get('model', 'gpt-4')
            )

        elif provider_type == 'ollama':
            return OllamaProvider(
                model=kwargs.get('model', 'llama3.2'),
                host=kwargs.get('host', 'http://localhost:11434')
            )

        else:
            raise ValueError(f"Unknown provider: {provider_type}. Use 'claude', 'openai', or 'ollama'")

    @staticmethod
    def auto_detect():
        """
        Auto-detect available provider

        Priority:
        1. Claude (if API key available)
        2. OpenAI (if API key available)
        3. Ollama (if running locally)

        Returns:
            AIProvider instance or None
        """
        # Try Claude
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                return ClaudeProvider()
            except:
                pass

        # Try OpenAI
        if os.getenv("OPENAI_API_KEY"):
            try:
                return OpenAIProvider()
            except:
                pass

        # Try Ollama
        ollama = OllamaProvider()
        if ollama.is_available():
            return ollama

        return None


# Test function
if __name__ == "__main__":
    print("Testing AI Providers...\n")

    # Test Ollama
    print("1. Testing Ollama (Local - FREE)...")
    ollama = OllamaProvider()

    if ollama.is_available():
        print("✅ Ollama is running!")
        models = ollama.list_models()
        print(f"📦 Available models: {models}")

        if models:
            print("\n🧪 Testing generation...")
            result = ollama.generate("Say hello in one sentence")
            if result['success']:
                print(f"✅ Response: {result['content']}")
            else:
                print(f"❌ Error: {result['error']}")
    else:
        print("❌ Ollama not running")
        print("   Start with: ollama serve")

    # Test auto-detect
    print("\n2. Auto-detecting provider...")
    provider = AIProviderFactory.auto_detect()
    if provider:
        print(f"✅ Found: {provider.name}")
    else:
        print("❌ No providers available")
