# Invisible AI Assistant - Quick Start

## 5-Minute Setup

### 1. Install Tesseract (Required)
```bash
brew install tesseract
```

### 2. Add Your API Key
```bash
cd ~/Desktop/invisible-ai-assistant
nano .env
```

Add this line:
```
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

Get your key from: https://console.anthropic.com/

### 3. Run It!

**Terminal 1 - Start Server:**
```bash
./start_server.sh
```

**Terminal 2 - Start Client:**
```bash
./start_invisible.sh
```

**Now press F1 anywhere!**

---

## What Just Happened?

1. **Server Started** - Your main computer is now running the AI brain
2. **Client Connected** - Your user computer connected to the server
3. **Hotkey Registered** - System is listening for F1
4. **Ready to Go** - Press the hotkey anywhere to activate!

---

## Try These:

### Test 1: Normal Mode (Default)
1. Open a text document or webpage
2. Press **F1**
3. Watch the AI overlay appear on YOUR screen!

### Test 2: Server Mode (Video Call Privacy) 🎥
1. Copy this text: `/server What is 2+2?`
2. Press **F1**
3. YOUR SCREEN: Stays clean! Nothing appears!
4. SERVER WINDOW: Shows "4" and explanation
5. Perfect for presentations and video calls!

### Test 3: Both Mode (Multi-Monitor)
1. Copy: `/both Explain something`
2. Press **F1**
3. YOUR SCREEN: Overlay appears
4. SERVER WINDOW: Also shows it
5. See response in both places!

### Test 4: Silent Mode (Maximum Privacy)
1. Copy: `/silent Private question here`
2. Press **F1**
3. YOUR SCREEN: Nothing
4. SERVER WINDOW: Nothing
5. Check server terminal logs for response

---

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **F1** | Activate AI Assistant |
| **ESC** | Close response overlay |
| **Ctrl+C** | Copy response to clipboard (when overlay is open) |
| **Ctrl+C** | Stop agent (in terminal) |

---

## Troubleshooting

**"Tesseract not found"**
```bash
# Check if installed:
tesseract --version

# If not, install:
brew install tesseract
```

**"Connection refused"**
- Make sure server is running first
- Check that both server and client use same network

**"Permission denied" (keyboard)**
- macOS: System Preferences → Security & Privacy → Privacy → Accessibility
- Add your Terminal app

---

## Next Steps

- ✅ Test the basic functionality
- 📖 Read [SETUP.md](SETUP.md) for advanced configuration
- 🚀 Use it daily and see the magic!
- 🔧 Customize hotkey, overlay, and more

---

**Need Help?**
See [README.md](README.md) for full documentation
