# Ollama Setup - FREE Local AI (No API Keys!)

## 🎉 Use Invisible AI Assistant 100% FREE with Ollama!

**No API keys. No costs. No cloud. Just you and your computer.**

---

## What is Ollama?

Ollama is a local AI server that runs powerful language models (Llama, Mistral, etc.) **completely on your computer**.

**Benefits:**
- ✅ **100% FREE** - No API costs ever
- ✅ **100% Private** - Nothing leaves your computer
- ✅ **No Internet Required** - After initial download
- ✅ **No API Keys** - Zero configuration headaches
- ✅ **Fast** - Runs locally, no network latency

---

## Quick Start (5 Minutes)

### Step 1: Install Ollama

**macOS:**
```bash
# Download and install from:
https://ollama.ai/download

# Or use Homebrew:
brew install ollama
```

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
```bash
# Download installer from:
https://ollama.ai/download
```

### Step 2: Start Ollama

```bash
ollama serve
```

This starts the Ollama server on `http://localhost:11434`

**Keep this running!** Leave the terminal open.

### Step 3: Download a Model

Open a **NEW terminal** and run:

```bash
# Recommended: Llama 3.2 (3B - Fast, good quality)
ollama pull llama3.2

# Or try others:
ollama pull mistral        # Mistral 7B - Great for coding
ollama pull codellama      # Code-specialized
ollama pull llama3.2:1b    # Tiny, super fast
```

**First time?** Download takes 2-5 minutes depending on model size.

### Step 4: Test It

```bash
ollama run llama3.2

# Type a question:
>>> Hello, who are you?

# Press Ctrl+D to exit
```

### Step 5: Use with Invisible AI

```bash
cd ~/Desktop/invisible-ai-assistant

# Start server (will auto-detect Ollama!)
./start_server.sh

# Start client
./start_invisible.sh

# Press F1 - you're using FREE local AI! 🎉
```

---

## Available Models

### Recommended for Invisible AI:

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| **llama3.2** | 3GB | ⚡⚡⚡ | ⭐⭐⭐⭐ | General use (RECOMMENDED) |
| **llama3.2:1b** | 1GB | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ | Ultra-fast, low RAM |
| **mistral** | 4GB | ⚡⚡ | ⭐⭐⭐⭐⭐ | High quality |
| **codellama** | 4GB | ⚡⚡ | ⭐⭐⭐⭐ | Coding assistance |
| **phi3** | 2GB | ⚡⚡⚡⚡ | ⭐⭐⭐⭐ | Balanced |

### Download Any Model:

```bash
ollama pull <model-name>

# Examples:
ollama pull llama3.2
ollama pull mistral
ollama pull codellama
```

### List Downloaded Models:

```bash
ollama list
```

---

## Configuration

### Change Default Model

Edit `server/config.yaml`:

```yaml
ai:
  ollama:
    model: "mistral"  # Change from llama3.2 to your preferred model
    host: "http://localhost:11434"
```

### Use Different Port

If Ollama runs on a different port:

```yaml
ai:
  ollama:
    host: "http://localhost:12345"  # Your custom port
```

---

## Troubleshooting

### "Ollama not running"

**Problem:** Server can't connect to Ollama

**Solution:**
```bash
# Start Ollama in terminal:
ollama serve

# Keep it running!
```

### "Model not found"

**Problem:** You haven't downloaded the model yet

**Solution:**
```bash
ollama pull llama3.2
```

### Slow Responses

**Problem:** Model is too big for your hardware

**Solution:** Use a smaller model:
```bash
ollama pull llama3.2:1b  # Tiny, super fast
```

Then update `server/config.yaml`:
```yaml
ai:
  ollama:
    model: "llama3.2:1b"
```

### "Connection refused"

**Problem:** Ollama not running or wrong port

**Solutions:**
1. Check Ollama is running: `curl http://localhost:11434/api/tags`
2. Check the port in config matches Ollama's port

---

## Performance Tips

### For Best Speed:

1. **Use smaller models:**
   - `llama3.2:1b` - Lightning fast
   - `phi3` - Good balance

2. **Close other apps** - Free up RAM

3. **Use SSD** - Faster model loading

### For Best Quality:

1. **Use larger models:**
   - `mistral` - Excellent quality
   - `llama3.2` - Good default

2. **Increase max_tokens** in config:
```yaml
ai:
  max_tokens: 4000  # Longer responses
```

---

## Comparing Providers

| Feature | Ollama | Claude | OpenAI |
|---------|--------|--------|---------|
| **Cost** | FREE ✅ | $$ Paid | $$$ Paid |
| **Privacy** | 100% Local ✅ | Cloud | Cloud |
| **Speed** | Fast ⚡ | Very Fast | Very Fast |
| **Quality** | Good ⭐⭐⭐⭐ | Excellent ⭐⭐⭐⭐⭐ | Excellent ⭐⭐⭐⭐⭐ |
| **Setup** | Simple | API Key needed | API Key needed |
| **Offline** | Works ✅ | Needs internet | Needs internet |

---

## Auto-Detection Priority

The server automatically tries providers in this order:

1. **Claude** - If `ANTHROPIC_API_KEY` in `.env`
2. **OpenAI** - If `OPENAI_API_KEY` in `.env`
3. **Ollama** - If running locally

**Want to force Ollama?**
- Just don't set API keys in `.env`
- Ollama will be used automatically!

---

## Common Commands

```bash
# Start Ollama server
ollama serve

# Download a model
ollama pull llama3.2

# List installed models
ollama list

# Test a model
ollama run llama3.2

# Remove a model
ollama rm llama3.2

# Check status
curl http://localhost:11434/api/tags
```

---

## FAQ

**Q: Do I need internet after downloading?**
A: No! Works 100% offline after model download.

**Q: How much disk space do I need?**
A: 1-7GB per model. `llama3.2:1b` is only 1GB!

**Q: Can I use multiple models?**
A: Yes! Download several, switch in config.

**Q: Is Ollama as good as Claude/GPT?**
A: Quality is good but not quite as high. Trade-off: FREE and private!

**Q: Can I use this for production?**
A: Yes! Many companies use Ollama for privacy-sensitive deployments.

**Q: Does it work on older computers?**
A: Yes! Use `llama3.2:1b` for lower-end hardware.

---

## Next Steps

1. ✅ Install Ollama
2. ✅ Download a model
3. ✅ Start `ollama serve`
4. ✅ Run `./start_server.sh`
5. ✅ Press F1 - Enjoy FREE AI!

---

**Resources:**
- Ollama Website: https://ollama.ai
- Model Library: https://ollama.ai/library
- GitHub: https://github.com/ollama/ollama

---

**Version:** 0.4.0
**Feature:** FREE Local AI Support
**Status:** Production Ready 🎉
