"""
Screen capture and OCR functionality
"""

import io
import os
from datetime import datetime

import pyautogui
from PIL import Image, ImageGrab


# Try to use Apple's Vision framework first (better accuracy, ships with
# macOS, no external binary). Fall back to Tesseract via pytesseract on
# error or non-macOS systems.
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
        """Extract text from image using OCR. Prefers Vision (macOS),
        falls back to Tesseract."""
        if image is None:
            return ""
        text = ""
        if _VISION_AVAILABLE:
            try:
                text = _ocr_with_vision(image)
            except Exception as e:
                print(f"[WARN] Vision OCR failed: {e}; falling back to Tesseract")
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
