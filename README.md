# Invisible AI Assistant

A personal distributed computing system that enables seamless interaction with AI across multiple devices.

**Press F1 anywhere to summon your AI assistant!**

## ✨ Features

- 🔥 **Invisible Operation** - Press F1 anywhere, AI responds instantly
- 🎥 **Smart Display Routing** - Show on client/server/both/silent (perfect for video calls!)
- 👁️ **Screen Awareness** - Sees what's on your screen via OCR
- 📋 **Clipboard Integration** - Automatically includes clipboard context
- 💻 **Distributed Computing** - Lightweight client, powerful server
- 🔒 **Privacy-First** - All processing on your local network
- 🎨 **Transparent Overlay** - Responses appear over your work
- ⚡ **Real-time** - WebSocket communication for instant responses

## 🚀 Quick Start

**📖 For detailed setup instructions, see [SETUP.md](SETUP.md)**

### 1. Setup Environment

```bash
cd invisible-ai-assistant

# Create .env file from example
cp .env.example .env

# Edit .env and add your Claude API key
# ANTHROPIC_API_KEY=your-key-here
```

### 2. Get Your Claude API Key

1. Go to https://console.anthropic.com/
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new key and copy it
5. Paste it in your `.env` file

### 3. Install Tesseract OCR (Required for Screen Capture)

```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr
```

### 4. Start the Server (Main Computer)

```bash
./start_server.sh
```

### 5. Start the Client (User Computer)

**Full Featured Mode (Background + Hotkey):**
```bash
./start_invisible.sh
```

Now press **F1** anywhere to activate!

**Or Interactive Mode (for testing):**
```bash
source venv/bin/activate
python client/invisible_agent.py --mode interactive
```

**Or Basic Mode (no screen capture):**
```bash
./start_client.sh
```

## 📁 Project Structure

```
invisible-ai-assistant/
├── client/                      # User computer agent
│   ├── agent.py                # Basic client (MVP)
│   ├── invisible_agent.py      # Full featured client
│   ├── screen_capture.py       # Screen capture + OCR
│   ├── keyboard_listener.py    # Hotkey detection
│   └── overlay_display.py      # Transparent overlay UI
├── server/                      # Main computer brain
│   ├── main_server.py          # WebSocket server + AI
│   └── config.yaml             # Server configuration
├── start_server.sh             # Quick start server
├── start_client.sh             # Quick start basic client
├── start_invisible.sh          # Quick start full client
├── SETUP.md                    # Detailed setup guide
├── README.md                   # This file
└── .env                        # Your API keys (you create this)
```

## 🔧 Configuration

### Server Configuration
Edit `server/config.yaml` to change:
- Port number
- AI model
- Max tokens
- Logging level

### Client Configuration
Edit `.env` to set:
- `MAIN_COMPUTER_IP` - IP address of your main computer
- `SERVER_PORT` - Port number (default: 8765)

## 🎯 Current Features

### ✅ Fully Working
- **WebSocket Communication** - Real-time client-server connection
- **Claude AI Integration** - Powered by Claude Sonnet 4.5
- **Screen Capture + OCR** - Reads text from your screen
- **Keyboard Shortcuts** - Global hotkey (F1) activation
- **Smart Display Routing** - 4 modes: client/server/both/silent
- **Server Display Window** - Shows responses on main computer
- **Transparent Overlay** - Beautiful response display on client
- **Clipboard Integration** - Automatic context from clipboard
- **Background Mode** - Runs invisibly, always ready
- **Interactive Mode** - Terminal-based testing mode
- **Multi-Client Support** - Multiple devices connect to one server
- **Error Handling** - Graceful error recovery

### 🚧 Coming Next (Phase 3+)

- Auto-start on boot (system service)
- Advanced context filtering (exclude sensitive data)
- Multi-modal input (voice, image analysis)
- Custom commands and workflows
- Response caching for speed
- Analytics dashboard
- Security encryption (TLS/SSL)
- API cost tracking

## 🐛 Troubleshooting

### "Connection refused"
- Make sure the server is running
- Check the IP address is correct
- Check firewall settings

### "ANTHROPIC_API_KEY not found"
- Make sure you created `.env` file
- Make sure you added your API key
- Make sure there are no spaces around the `=` sign

### "Module not found"
- Make sure you activated the virtual environment: `source venv/bin/activate`
- Try reinstalling: `pip install -r requirements.txt`

## 💡 Usage Examples

### Background Mode (Invisible)
```bash
# Start server
./start_server.sh

# Start client in another terminal
./start_invisible.sh

# Now anywhere in your system:
# 1. Open a text document
# 2. Press F1
# 3. AI reads your screen and helps!
```

### 🎥 Video Call Mode (NEW!)

**Perfect for Zoom, Teams, Google Meet:**

```bash
# You're in a video call, sharing your screen
# Need AI help but don't want audience to see it

1. Copy: /server How do I explain this technical concept?
2. Press F1
3. YOUR SCREEN: Stays completely clean ✅
4. SERVER DISPLAY: Shows AI response ✅
5. AUDIENCE: Sees nothing! 🎉
```

**See [DISPLAY_MODES.md](DISPLAY_MODES.md) for complete guide**

### Real-World Professional Scenarios

**Scenario 1: Sales Presentation**
1. You're presenting to a client, screen shared
2. Client asks unexpected technical question
3. Copy: `/server Quick answer for [their question]`
4. Press F1
5. Read answer from server display (second monitor)
6. Client sees nothing, you look prepared!

**Scenario 2: Code Review Meeting**
1. Reviewing code on screen share
2. Teammate asks about a pattern you're unsure of
3. Copy: `/server Explain [pattern name]`
4. Press F1
5. Get instant explanation on server, share it verbally

**Scenario 3: Live Coding Session**
1. Teaching/demonstrating code live
2. Hit an error you don't recognize
3. Copy error message + `/server`
4. Press F1
5. Solution appears on your other monitor
6. Audience thinks you're a genius!

**Scenario 4: Regular Work**
1. Just coding normally
2. Press F1 (no modifier)
3. Overlay appears on YOUR screen
4. Quick help without switching apps

### Display Mode Quick Reference

| Copy This | Your Screen | Server Display | Use Case |
|-----------|-------------|----------------|----------|
| *(nothing)* | ✅ Shows | ❌ Nothing | Normal work |
| `/server question` | ❌ **Nothing** | ✅ Shows | Video calls, presentations |
| `/both question` | ✅ Shows | ✅ Shows | Multi-monitor setup |
| `/silent question` | ❌ Nothing | ❌ Nothing | Max privacy, logs only |

### Interactive Mode
```bash
./start_invisible.sh --mode interactive

You: What's on my screen?
(AI analyzes screen and responds)

You: /server Explain this code
(Response shows ONLY on server)
```

## 📝 License

Personal use project - See project plan for details

## 🤝 Contributing

This is currently a personal project. See the full project plan PDF for roadmap and future enhancements.

---

**Version:** 0.3.0 (Professional Edition)
**Status:** Production Ready
**Last Updated:** 2025-12-22

## 🎯 What's New in v0.3.0

- 🎥 **Smart Display Routing** - 4 modes for privacy control
- 🖥️ **Server Display Window** - See responses on main computer
- 🔒 **Video Call Privacy** - `/server` mode keeps screen clean
- 📊 **Display Modifiers** - `/server`, `/both`, `/silent`, `/client`
- ✨ All features from v0.2.0 (Screen OCR, Hotkeys, Overlay, etc.)

## 🎯 What's New in v0.2.0

- ✨ Screen capture with OCR
- ⌨️ Global keyboard shortcuts (F1)
- 🎨 Transparent overlay display
- 🔄 Background service mode
- 📊 Enhanced context capture
- 🚀 Production-ready features

See [SETUP.md](SETUP.md) for setup and [DISPLAY_MODES.md](DISPLAY_MODES.md) for display routing.
