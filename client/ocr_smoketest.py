"""
Smoke test for the Windows OCR path (_ocr_with_winrt in screen_capture.py).

Renders an image with known text, runs it through the real WinRT OCR
function, and asserts the text comes back. Exits non-zero on failure so CI
catches regressions in the Windows.Media.Ocr code path without a human.

Exit semantics:
  0  PASS, or SKIP (non-Windows host, or no OCR language pack installed)
  1  FAIL (winrt import broke, or OCR ran but produced wrong text)

The "no language pack -> skip" case matters on CI: a bare Windows runner may
lack an OCR language, which is an environment gap, not a code defect.
"""

import sys

from PIL import Image, ImageDraw, ImageFont


EXPECTED = "WARDEN OCR TEST 12345"


def _make_image(text):
    img = Image.new("RGB", (900, 200), color="white")
    draw = ImageDraw.Draw(img)
    font = None
    for candidate in (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        "arial.ttf",
    ):
        try:
            font = ImageFont.truetype(candidate, 56)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()
    draw.text((40, 70), text, fill="black", font=font)
    return img


def _norm(s):
    return "".join(c for c in (s or "").upper() if c.isalnum())


def main():
    if not sys.platform.startswith("win"):
        print("[SKIP] OCR smoke test only runs on Windows")
        return 0

    sys.path.insert(0, "client")
    import screen_capture

    if not screen_capture._WINRT_AVAILABLE:
        print("[FAIL] winrt OCR modules failed to import")
        return 1

    # If no OCR language pack is installed, the engine can't be created. That's
    # an environment gap on this runner, not a defect — skip rather than fail.
    from winrt.windows.media.ocr import OcrEngine
    if OcrEngine.try_create_from_user_profile_languages() is None:
        print("[SKIP] no OCR language pack on this machine; cannot validate output")
        return 0

    result = screen_capture._ocr_with_winrt(_make_image(EXPECTED))
    print(f"[INFO] OCR returned: {result!r}")

    if _norm(EXPECTED) in _norm(result):
        print("[PASS] WinRT OCR recognized the expected text")
        return 0
    print(f"[FAIL] expected to find {EXPECTED!r} in OCR output")
    return 1


if __name__ == "__main__":
    sys.exit(main())
