"""
AI Provider Abstraction Layer
Supports: Claude (Anthropic), OpenAI (ChatGPT), Ollama (Local)
"""

import os
import time
import random
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

    # HTTP statuses worth retrying: rate limit + transient server/overload.
    # 529 is Anthropic's "Overloaded" — common during peak demand.
    _RETRY_STATUSES = {429, 500, 502, 503, 504, 529}
    # Up to this many attempts per model before falling back to the next.
    _MAX_ATTEMPTS_PER_MODEL = 4

    def __init__(self, api_key=None, model="claude-sonnet-4-6"):
        super().__init__()
        self.name = "Claude (Anthropic)"
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        # If the primary model is overloaded, fall back to a lighter model that
        # usually has spare capacity. A Haiku answer beats a 529 error. Override
        # the chain with WARDEN_FALLBACK_MODELS (comma-separated) if needed.
        fallback_env = os.getenv("WARDEN_FALLBACK_MODELS", "claude-haiku-4-5-20251001")
        self.fallback_models = [m.strip() for m in fallback_env.split(",") if m.strip()]

        # Bump default timeout (default ~60s can be too short on slow links).
        # We do our own retry/backoff + model fallback below, so disable the
        # SDK's internal retries to keep timing predictable.
        self.client = Anthropic(api_key=self.api_key, timeout=120.0, max_retries=0)

    def is_available(self):
        """Check if Claude is available"""
        return self.api_key is not None

    @classmethod
    def _is_retryable(cls, exc):
        """True for transient overload/rate-limit/5xx errors worth retrying."""
        status = getattr(exc, "status_code", None)
        if status in cls._RETRY_STATUSES:
            return True
        s = str(exc).lower()
        return "overloaded" in s or "529" in s or "rate limit" in s

    def generate(self, prompt, max_tokens=2000, system=None, history=None, pinned_context=None):
        """Generate response using Claude.

        `history` — prior {role, content} dicts; new `prompt` becomes the
            final user turn.
        `pinned_context` — persistent user-set text (their study material,
            notes, etc.). Sent as a separate cacheable system block so the
            tokens are paid for once per 5-minute window.

        On transient overload (HTTP 529) we retry with exponential backoff,
        then fall back to a lighter model — so a busy spell on Anthropic's
        side surfaces as a slightly slower answer instead of an error.
        """
        messages = list(history) if history else []
        messages.append({"role": "user", "content": prompt})

        system_blocks = []
        if system:
            system_blocks.append({
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            })
        if pinned_context:
            system_blocks.append({
                "type": "text",
                "text": f"Persistent context the user has pinned:\n{pinned_context}",
                "cache_control": {"type": "ephemeral"},
            })

        models = [self.model] + [m for m in self.fallback_models if m != self.model]
        last_exc = None

        for model in models:
            kwargs = dict(model=model, max_tokens=max_tokens, messages=messages)
            if system_blocks:
                kwargs["system"] = system_blocks

            for attempt in range(self._MAX_ATTEMPTS_PER_MODEL):
                try:
                    message = self.client.messages.create(**kwargs)

                    usage = message.usage
                    cache_read = getattr(usage, 'cache_read_input_tokens', 0) or 0
                    cache_creation = getattr(usage, 'cache_creation_input_tokens', 0) or 0
                    tokens_used = usage.input_tokens + usage.output_tokens
                    if cache_read or cache_creation:
                        print(f"[cache] read={cache_read} created={cache_creation}")
                    if model != self.model:
                        print(f"[claude] primary overloaded — served by fallback model {model}")

                    return {
                        'success': True,
                        'content': message.content[0].text,
                        'model': model,
                        'provider': 'claude',
                        'tokens_used': tokens_used,
                    }

                except Exception as e:
                    last_exc = e
                    if self._is_retryable(e) and attempt < self._MAX_ATTEMPTS_PER_MODEL - 1:
                        delay = min(8.0, 0.8 * (2 ** attempt)) + random.uniform(0, 0.4)
                        print(f"[claude] {model} overloaded (attempt {attempt + 1}); "
                              f"retrying in {delay:.1f}s")
                        time.sleep(delay)
                        continue
                    if self._is_retryable(e):
                        # Out of attempts on this model — fall back to the next.
                        print(f"[claude] {model} still overloaded after "
                              f"{self._MAX_ATTEMPTS_PER_MODEL} attempts; trying fallback")
                        break
                    # A non-transient error (bad key, invalid request) — retrying
                    # or falling back won't help, so surface it immediately.
                    return {'success': False, 'error': str(e), 'provider': 'claude'}

        return {'success': False, 'error': str(last_exc), 'provider': 'claude'}


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

    def generate(self, prompt, max_tokens=2000, system=None, history=None, pinned_context=None):
        """Generate response using OpenAI"""
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            if pinned_context:
                messages.append({"role": "system", "content": f"Pinned context:\n{pinned_context}"})
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

    def generate(self, prompt, max_tokens=2000, system=None, history=None, pinned_context=None):
        """Generate response using Ollama. (history is currently flattened
        into the prompt — Ollama's /api/generate doesn't take messages.)"""
        if pinned_context:
            prompt = f"Pinned context:\n{pinned_context}\n\n{prompt}"
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
