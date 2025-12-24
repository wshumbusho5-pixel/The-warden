# Display Modes - Smart Response Routing

## Overview

Control where AI responses appear - perfect for video calls, presentations, or privacy!

---

## The 4 Display Modes

### 1. `/client` (Default)
**Shows:** ✅ Your screen ONLY
**Server:** ❌ Nothing
**Use:** Normal usage

### 2. `/server` ⭐ **PRIVACY MODE**
**Shows:** ❌ Nothing on your screen!
**Server:** ✅ Main computer ONLY
**Use:** Video calls, screen sharing, presentations

### 3. `/both`
**Shows:** ✅ Your screen
**Server:** ✅ Main computer
**Use:** Multi-monitor setups

### 4. `/silent`
**Shows:** ❌ Nothing anywhere
**Server:** ❌ Nothing (logged only)
**Use:** Maximum privacy

---

## How It Works

### `/server` Mode - Privacy for Video Calls

**YOU ARE IN A ZOOM CALL, SHARING YOUR SCREEN:**

1. Copy this: `/server How do I explain recursion?`
2. Press **F1**
3. **YOUR SCREEN:** Nothing appears! Clean! 🎉
4. **SERVER SCREEN:** Response shows in a window
5. **ZOOM AUDIENCE:** Sees absolutely nothing!

**Perfect for:**
- Video calls (Zoom, Teams, Meet)
- Live presentations
- Screen sharing sessions
- Teaching/training while getting AI help

---

## Quick Examples

### Video Call Scenario
```
SITUATION: In Zoom call, screen shared, stuck on a question

COPY: /server What's the answer to this technical question?
PRESS: F1

YOUR SCREEN (what Zoom sees): Nothing! Completely clean!
SERVER SCREEN: Full AI response in a window
```

### Regular Usage
```
SITUATION: Working alone, need help

JUST PRESS: F1 (no modifier needed)

YOUR SCREEN: Overlay with AI response
SERVER SCREEN: Nothing
```

### Both Screens
```
SITUATION: Want to see on laptop AND desktop monitor

COPY: /both Explain this code
PRESS: F1

YOUR SCREEN: Overlay shows
SERVER SCREEN: Display window shows
```

### Maximum Privacy
```
SITUATION: In public, very sensitive question

COPY: /silent Private question here
PRESS: F1

YOUR SCREEN: Nothing
SERVER SCREEN: Nothing visible
SERVER LOGS: Response logged (check terminal)
```

---

## Server Display Window

When server starts, this window opens automatically:

```
┌──────────────────────────────────────────┐
│  🖥️ Server Display - AI Responses        │
├──────────────────────────────────────────┤
│  Responses: 3                            │
├──────────────────────────────────────────┤
│                                          │
│  Response #1 (Client: 12345)             │
│  The capital of France is Paris...       │
│  Model: claude-sonnet-4 | Tokens: 150   │
│                                          │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                          │
│  Response #2 (Client: 12345)             │
│  Recursion is a programming...           │
│  Model: claude-sonnet-4 | Tokens: 250   │
│                                          │
├──────────────────────────────────────────┤
│  [Clear]  [Copy Last]        [Minimize]  │
└──────────────────────────────────────────┘
```

This appears **ONLY when using `/server` or `/both` modes.**

---

## Complete Guide

| Mode | Copy This | Your Screen | Server Display | Use When |
|------|-----------|-------------|----------------|----------|
| **Default** | *(nothing)* | ✅ Overlay | ❌ Nothing | Working alone |
| **Server** | `/server question` | ❌ **NOTHING!** | ✅ Window | Video calls, sharing |
| **Both** | `/both question` | ✅ Overlay | ✅ Window | Multi-monitor |
| **Silent** | `/silent question` | ❌ Nothing | ❌ Nothing | Maximum privacy |

---

## Real Example - Video Call

**Before:**
```
You: *shares screen in Zoom*
You: *presses F1*
AI overlay: *POPS UP ON SCREEN*
Zoom: *EVERYONE SEES YOUR AI HELPER!* 😱
```

**After (using /server):**
```
You: *copies "/server how do I explain this?"*
You: *presses F1*
Your screen: *stays completely clean* ✅
Server screen: *shows response* ✅
Zoom audience: *sees NOTHING* 🎉
```

---

## How to Use

### Method 1: Clipboard (Recommended)
1. Copy: `/server Your question here`
2. Press F1
3. Done!

### Method 2: On-Screen Text
1. Have `/server` visible on your screen
2. Press F1
3. OCR reads it and routes accordingly

---

## Tips for Video Calls

### Before the Call
1. Start server: `./start_server.sh`
2. Server display window opens
3. Position it on a monitor that's NOT being shared

### During the Call
1. When you need help, copy: `/server question`
2. Press F1
3. Look at your other monitor (server display)
4. Audience sees nothing!

### Pro Tip
Keep a text file with `/server` ready to copy quickly!

---

## FAQ

**Q: Does `/server` show ANYTHING on my screen?**
A: **NO!** Absolutely nothing. Your screen stays 100% clean.

**Q: Where does the response go?**
A: Only to the server display window (on your main computer).

**Q: Can I use this for presentations?**
A: **YES!** Perfect for presentations. Audience sees nothing.

**Q: What if I'm sharing my entire screen including server?**
A: Use `/silent` mode - nothing shows anywhere. Check logs later.

**Q: Do I need to type `/server` every time?**
A: Only when you want server-only display. Otherwise just press F1 normally.

---

## Testing It

**Test 1: Normal Mode**
```bash
# Just press F1
# Response shows on YOUR screen in overlay
```

**Test 2: Server Mode**
```bash
# Copy: /server What is 2+2?
# Press F1
# YOUR SCREEN: Nothing!
# SERVER: Shows "4" in display window
```

**Test 3: Both Mode**
```bash
# Copy: /both Test message
# Press F1
# YOUR SCREEN: Overlay appears
# SERVER: Display window shows it too
```

---

**Version:** 0.3.0
**Feature:** Privacy-First Display Routing
**Status:** Ready for Video Calls! 🎥
