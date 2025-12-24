"""
Screen capture and OCR functionality
"""

import pyautogui
import pytesseract
from PIL import Image, ImageGrab
import io
from datetime import datetime


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
        """
        Extract text from image using OCR

        Args:
            image: PIL Image object

        Returns:
            Extracted text as string
        """
        try:
            if image is None:
                return ""

            # Use pytesseract to extract text
            text = pytesseract.image_to_string(image)
            self.last_text = text
            return text.strip()
        except Exception as e:
            print(f"[ERROR] OCR failed: {e}")
            print(f"[INFO] Make sure tesseract is installed:")
            print(f"       macOS: brew install tesseract")
            print(f"       Ubuntu: sudo apt-get install tesseract-ocr")
            print(f"       Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
            return ""

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
