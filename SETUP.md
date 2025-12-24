# Invisible AI Assistant - Complete Setup Guide

## Prerequisites

Before running the Invisible AI Assistant, you need to install:

1. **Python 3.9+**
2. **Tesseract OCR** (for screen text extraction)
3. **Claude API Key**

---

## Step 1: Install Tesseract OCR

### macOS
```bash
brew install tesseract
```

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

### Windows
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

Add tesseract to your PATH after installation.

### Verify Installation
```bash
tesseract --version
```

You should see version information if installed correctly.

---

## Step 2: Get Your Claude API Key

1. Go to https://console.anthropic.com/
2. Create an account or sign in
3. Navigate to **API Keys**
4. Click **Create Key**
5. Copy the API key
6. Keep it safe - you'll need it in the next step

---

## Step 3: Configure the Project

### Add Your API Key

Edit the `.env` file:
```bash
cd ~/Desktop/invisible-ai-assistant
nano .env
```

Add your API key:
```
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
```

Save and exit (Ctrl+X, then Y, then Enter)

### Configure Server IP (if using multiple computers)

If you want to connect from other computers:

1. Find your main computer's IP address:
   ```bash
   # macOS/Linux:
   ifconfig | grep "inet "

   # Or use:
   ipconfig getifaddr en0  # macOS
   hostname -I             # Linux
   ```

2. Update `.env` on CLIENT computers:
   ```
   MAIN_COMPUTER_IP=192.168.1.100  # Use your actual IP
   ```

---

## Step 4: Install Python Dependencies

```bash
cd ~/Desktop/invisible-ai-assistant
source venv/bin/activate
pip install -r requirements.txt
```

---

## Step 5: Test the Installation

### Test Tesseract
```bash
python -c "import pytesseract; print('Tesseract OK')"
```

### Test Screen Capture
```bash
cd ~/Desktop/invisible-ai-assistant
source venv/bin/activate
python -c "from client.screen_capture import ScreenCapture; sc = ScreenCapture(); print('Screen capture OK')"
```

---

## Running the System

### Mode 1: Background Mode (Invisible Operation)

**On Main Computer (Server):**
```bash
./start_server.sh
```

**On User Computer (Client):**
```bash
./start_invisible.sh
```

Now press **F1** anywhere to activate the AI!

### Mode 2: Interactive Mode (Testing)

**On Main Computer (Server):**
```bash
./start_server.sh
```

**On User Computer (Client):**
```bash
source venv/bin/activate
python client/invisible_agent.py --mode interactive
```

Type questions directly in the terminal.

### Mode 3: Simple Client (MVP - No Screen Capture)

If you just want basic functionality without screen capture:

```bash
./start_client.sh
```

---

## Features Available

### ✅ Fully Working
- WebSocket client-server communication
- Claude AI integration (Sonnet 4.5)
- Screen capture with OCR
- Clipboard context
- Global keyboard shortcut (F1)
- Transparent overlay display
- Multi-client support
- Error handling

### 🚧 Coming Soon
- Auto-start on boot (system service)
- Advanced context filtering
- Multi-modal input (voice, images)
- Custom commands
- Analytics dashboard

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **F1** | Activate AI Assistant |
| **ESC** | Close overlay |
| **Ctrl+C** (in overlay) | Copy response |
| **Ctrl+C** (in terminal) | Stop agent |

---

## Troubleshooting

### "Tesseract not found"
- Make sure tesseract is installed: `tesseract --version`
- On macOS, you may need to specify the path:
  ```python
  import pytesseract
  pytesseract.pytesseract.tesseract_cmd = '/opt/homebrew/bin/tesseract'
  ```

### "Permission denied" for keyboard shortcuts
- On macOS: Grant accessibility permissions:
  - System Preferences → Security & Privacy → Privacy → Accessibility
  - Add Terminal (or your terminal app)

- On Linux: May need to run with sudo (not recommended for production)

### "Connection refused"
- Make sure server is running
- Check firewall settings
- Verify IP address in `.env`

### Screen capture returns empty text
- Make sure the screen has visible text
- Try with a text document or browser
- Check tesseract installation
- Screen might be too complex - OCR works best with clear text

### Overlay doesn't appear
- Check if tkinter is installed: `python -c "import tkinter"`
- On Linux, install: `sudo apt-get install python3-tk`

---

## System Requirements

### Main Computer (Server)
- **RAM**: 2GB+ available
- **CPU**: Any modern processor
- **Network**: Local network or VPN
- **Storage**: 500MB for dependencies

### User Computer (Client)
- **RAM**: 512MB+ available
- **CPU**: Any processor
- **Network**: Access to server
- **Storage**: 100MB for dependencies

---

## Security Notes

- All data stays on your local network
- API keys stored only on main computer
- Screen captures processed in real-time, not stored
- Use VPN for remote access
- Consider adding encryption for production use

---

## Next Steps

1. ✅ Complete this setup
2. ✅ Test with basic questions
3. ✅ Test screen capture feature
4. ✅ Customize hotkey if needed
5. 📝 Read the main README.md for advanced features
6. 🚀 Start using it daily!

---

## Need Help?

Check the main `README.md` file or review the project plan PDF for more details.

**Version:** 0.2.0 (Full Featured)
**Last Updated:** 2025-12-22
