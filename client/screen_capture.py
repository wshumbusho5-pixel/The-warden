"""
Screen capture and OCR functionality.

OCR resolution order: native OS API first (Vision on macOS,
Windows.Media.Ocr on Windows), then Tesseract as a portable fallback.
Native APIs ship with the OS, so a packaged client doesn't need Tesseract
installed separately — that's only for Linux or stripped-down boxes.
"""

import io
import os
import sys
from datetime import datetime

import pyautogui
from PIL import Image, ImageGrab


# macOS: Vision framework. Ships with the OS, no external binary.
_VISION_AVAILABLE = False
try:
    from Vision import (
        VNRecognizeTextRequest,
        VNImageRequestHandler,
        VNRequestTextRecognitionLevelAccurate,
    )
    from Foundation import NSData
    from Quartz import (
        CGImageSourceCreateWithData,
        CGImageSourceCreateImageAtIndex,
    )
    _VISION_AVAILABLE = True
except Exception:
    _VISION_AVAILABLE = False


# Windows: Windows.Media.Ocr via Microsoft's pywinrt projection.
# Equivalent role to Vision on macOS — ships with Windows 10+, no extra binary.
_WINRT_AVAILABLE = False
if sys.platform.startswith('win'):
    try:
        import winrt.windows.media.ocr  # noqa: F401
        _WINRT_AVAILABLE = True
    except Exception:
        _WINRT_AVAILABLE = False

try:
    import pytesseract
    # Check well-known install paths per platform. On Windows the default
    # installer doesn't add Tesseract to PATH, so we have to point pytesseract
    # at it explicitly. On macOS/Linux these are the common Homebrew/apt paths.
    for _candidate in (
        '/opt/homebrew/bin/tesseract',                                 # macOS Apple Silicon
        '/usr/local/bin/tesseract',                                    # macOS Intel / Linux
        '/usr/bin/tesseract',                                          # Linux (apt)
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',               # Windows default
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',         # Windows 32-bit
    ):
        if os.path.isfile(_candidate):
            pytesseract.pytesseract.tesseract_cmd = _candidate
            break
except ImportError:
    pytesseract = None


def _ocr_with_vision(pil_image):
    """Run OCR via Apple's Vision framework. Returns extracted text."""
    buf = io.BytesIO()
    pil_image.save(buf, format='PNG')
    png_bytes = buf.getvalue()

    nsdata = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
    source = CGImageSourceCreateWithData(nsdata, None)
    if source is None:
        return ""
    cg_image = CGImageSourceCreateImageAtIndex(source, 0, None)
    if cg_image is None:
        return ""

    request = VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    handler = VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
    ok, _err = handler.performRequests_error_([request], None)
    if not ok:
        return ""

    results = request.results() or []
    lines = []
    for observation in results:
        candidates = observation.topCandidates_(1)
        if candidates:
            lines.append(candidates[0].string())
    return "\n".join(lines)


async def _winrt_ocr_async(pil_image):
    """Run a single OCR request via Windows.Media.Ocr. Internal — called from
    a worker thread by _ocr_with_winrt to avoid clashing with the client's
    own asyncio loop on the main thread."""
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.security.cryptography import CryptographicBuffer
    from winrt.windows.storage.streams import InMemoryRandomAccessStream

    buf = io.BytesIO()
    pil_image.save(buf, format='PNG')
    png_bytes = buf.getvalue()

    stream = InMemoryRandomAccessStream()
    ibuffer = CryptographicBuffer.create_from_byte_array(png_bytes)
    await stream.write_async(ibuffer)
    stream.seek(0)

    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        # No OCR language pack installed for the user's locale. Fall through
        # to the caller's Tesseract path.
        return ""
    ocr_result = await engine.recognize_async(bitmap)
    return "\n".join(line.text for line in ocr_result.lines)


def _ocr_with_winrt(pil_image):
    """Sync wrapper. WinRT OCR is async, but the OCR call sites are sync and
    sometimes nested inside the client's asyncio loop, so we run on a fresh
    worker thread with its own loop to keep them isolated."""
    if not _WINRT_AVAILABLE:
        return ""
    import asyncio
    import threading

    result = [""]
    error = [None]

    def run():
        try:
            result[0] = asyncio.run(_winrt_ocr_async(pil_image))
        except Exception as e:
            error[0] = e

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join()
    if error[0] is not None:
        print(f"[WARN] WinRT OCR failed: {error[0]}")
    return result[0]


def _ocr_with_tesseract(pil_image):
    if pytesseract is None:
        return ""
    try:
        return pytesseract.image_to_string(pil_image).strip()
    except Exception as e:
        print(f"[ERROR] Tesseract OCR failed: {e}")
        return ""


class ScreenCapture:
    """Handles screen capture and text extraction"""

    def __init__(self):
        self.last_capture = None
        self.last_text = None

    def capture_screen(self, region=None):
        """
        Capture the screen or a specific region

        Args:
            region: Tuple of (x, y, width, height) or None for full screen

        Returns:
            PIL Image object
        """
        try:
            if region:
                screenshot = ImageGrab.grab(bbox=region)
            else:
                screenshot = ImageGrab.grab()

            self.last_capture = screenshot
            return screenshot
        except Exception as e:
            print(f"[ERROR] Screen capture failed: {e}")
            return None

    def capture_active_window(self):
        """
        Capture only the active window

        Note: This is a simplified version. Full implementation would use
        platform-specific APIs to get active window bounds.
        """
        # For now, capture full screen
        # TODO: Implement platform-specific active window detection
        return self.capture_screen()

    def extract_text_from_image(self, image):
        """Extract text from image. Try the OS's native OCR first (Vision on
        macOS, Windows.Media.Ocr on Windows), Tesseract as last-resort fallback."""
        if image is None:
            return ""
        text = ""
        if _VISION_AVAILABLE:
            try:
                text = _ocr_with_vision(image)
            except Exception as e:
                print(f"[WARN] Vision OCR failed: {e}; falling back to Tesseract")
        elif _WINRT_AVAILABLE:
            try:
                text = _ocr_with_winrt(image)
            except Exception as e:
                print(f"[WARN] WinRT OCR failed: {e}; falling back to Tesseract")
        if not text:
            text = _ocr_with_tesseract(image)
        self.last_text = text
        return (text or "").strip()

    def capture_and_extract(self, region=None):
        """
        Capture screen and extract text in one call

        Args:
            region: Tuple of (x, y, width, height) or None for full screen

        Returns:
            Extracted text as string
        """
        screenshot = self.capture_screen(region)
        if screenshot:
            return self.extract_text_from_image(screenshot)
        return ""

    def capture_and_encode(self, region=None, max_long_side=1024, quality=80):
        """Capture the screen and return a JPEG payload ready to send to
        Anthropic's vision API.

        Args:
            region: Optional (x, y, w, h) crop.
            max_long_side: Longest-edge cap in pixels. 1024 keeps screen
                text readable while cutting vision-token cost ~40% vs
                1568. Anthropic bills roughly 1 token per 750 pixels, so
                a 1024x600 image is ~800 tokens vs ~2000 for 1568x900.
            quality: JPEG quality 0-100. 80 keeps text crisply readable on a
                typical screen while keeping the payload under ~150KB.

        Returns:
            {'media_type': 'image/jpeg', 'data': <base64 ascii str>} or None.
        """
        import base64
        screenshot = self.capture_screen(region)
        if screenshot is None:
            return None
        try:
            img = screenshot.convert("RGB")
            w, h = img.size
            longest = max(w, h)
            if longest > max_long_side:
                scale = max_long_side / float(longest)
                img = img.resize(
                    (int(w * scale), int(h * scale)),
                    Image.LANCZOS,
                )
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            data = base64.b64encode(buf.getvalue()).decode("ascii")
            return {"media_type": "image/jpeg", "data": data}
        except Exception as e:
            print(f"[ERROR] capture_and_encode failed: {e}")
            return None

    def get_screen_info(self):
        """Get screen resolution and basic info"""
        try:
            width, height = pyautogui.size()
            return {
                'width': width,
                'height': height,
                'resolution': f"{width}x{height}"
            }
        except Exception as e:
            print(f"[ERROR] Failed to get screen info: {e}")
            return {'width': 0, 'height': 0, 'resolution': 'unknown'}

    def capture_region_around_cursor(self, radius=200):
        """
        Capture a region around the current cursor position

        Args:
            radius: Pixels around cursor to capture

        Returns:
            Extracted text from region
        """
        try:
            # Get cursor position
            x, y = pyautogui.position()

            # Calculate region bounds
            left = max(0, x - radius)
            top = max(0, y - radius)
            right = x + radius
            bottom = y + radius

            # Capture region
            region = (left, top, right, bottom)
            return self.capture_and_extract(region)
        except Exception as e:
            print(f"[ERROR] Failed to capture cursor region: {e}")
            return ""

    def save_screenshot(self, filename=None):
        """Save the last screenshot to file"""
        if self.last_capture is None:
            print("[WARNING] No screenshot to save")
            return False

        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"

            self.last_capture.save(filename)
            print(f"[INFO] Screenshot saved to {filename}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to save screenshot: {e}")
            return False
