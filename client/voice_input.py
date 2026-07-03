"""
Push-to-toggle voice input for Warden.

Captures microphone audio locally, transcribes it with faster-whisper
(on-device — no audio ever leaves the machine), and hands the transcript
back through a callback. The callback is what the agent uses to spawn a
normal question request, so voice input reuses the exact same downstream
path as typing: capture screen → send question + image → answer overlay.

Hotkey flow:
    Ctrl+Alt+V (tap) → start recording, overlay shows "Recording…"
    Ctrl+Alt+V (tap) → stop, transcribe, fire the question

Model expected at whisper_models/base.en next to sys._MEIPASS in a
bundled app, or at <repo>/whisper_models/base.en for source runs.
Absence of the model, mic, or dependencies degrades gracefully — voice
is simply disabled and the user is told once at startup.
"""

import os
import sys
import threading


# Whisper's native input rate. Anything else needs resampling.
_SAMPLE_RATE = 16000


def find_model_path(model_name="base.en"):
    """Locate the bundled Whisper model directory.

    Preference: PyInstaller-extracted resources (sys._MEIPASS) first, then
    a repo-relative whisper_models/ for source runs.
    """
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "whisper_models", model_name))
    # source run: <repo>/whisper_models/base.en
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates.append(os.path.join(repo_root, "whisper_models", model_name))
    for path in candidates:
        # A valid CT2 model dir has a model.bin (weights) and config.json.
        if os.path.isdir(path) and os.path.isfile(os.path.join(path, "model.bin")):
            return path
    return None


class VoiceInput:
    """Voice capture + local transcription.

    Construct once at agent init; call toggle() from the hotkey handler.
    Emits state changes via `on_state_change("recording" | "transcribing"
    | "idle")` so the overlay can show a live indicator, and delivers the
    final transcript to `on_transcript_ready(text)`.
    """

    def __init__(self, model_path=None, on_transcript_ready=None):
        self.on_transcript_ready = on_transcript_ready
        self.on_state_change = None  # set by agent to wire the overlay
        self.enabled = False
        self._model = None
        self._model_lock = threading.Lock()
        self._frames = []
        self._stream = None
        self._recording = False

        self.model_path = model_path or find_model_path()
        if not self.model_path:
            print("[voice] no whisper model found; voice input disabled. "
                  "Expected whisper_models/base.en/model.bin bundled with "
                  "the app or in the repo root.")
            return

        # Import lazily so a broken faster-whisper/sounddevice install doesn't
        # take out the whole client at import time.
        try:
            import sounddevice  # noqa: F401
            import numpy  # noqa: F401
        except Exception as e:
            print(f"[voice] audio/numeric deps missing ({e}); voice disabled.")
            return

        try:
            from faster_whisper import WhisperModel  # noqa: F401
        except Exception as e:
            print(f"[voice] faster-whisper missing ({e}); voice disabled.")
            return

        self.enabled = True
        print(f"[voice] ready — model: {self.model_path}")

    # ---- public API -------------------------------------------------------

    def toggle(self):
        """Push-to-toggle: first tap starts capture, second tap ends it."""
        if not self.enabled:
            return
        if self._recording:
            self._stop_and_transcribe()
        else:
            self._start()

    @property
    def recording(self):
        return self._recording

    # ---- internals --------------------------------------------------------

    def _emit(self, state):
        cb = self.on_state_change
        if cb is not None:
            try:
                cb(state)
            except Exception as e:
                print(f"[voice] state callback failed: {e}")

    def _start(self):
        import sounddevice as sd
        try:
            self._frames = []
            self._recording = True
            self._stream = sd.InputStream(
                samplerate=_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            self._emit("recording")
            print("[voice] recording…")
        except Exception as e:
            print(f"[voice] mic open failed: {e}")
            self._recording = False
            self._stream = None
            self._emit("idle")

    def _audio_callback(self, indata, frames, time_info, status):
        # `status` carries under/overflow warnings — non-fatal, we ignore.
        if self._recording:
            # copy() because sounddevice reuses the underlying buffer.
            self._frames.append(indata.copy())

    def _stop_and_transcribe(self):
        import numpy as np

        self._recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

        if not self._frames:
            self._emit("idle")
            return

        audio = np.concatenate(self._frames, axis=0).flatten().astype("float32")
        self._frames = []

        # Whisper is happy with < 0.5s of audio but it's usually noise; skip.
        if len(audio) < _SAMPLE_RATE // 2:
            print("[voice] recording too short; skipping transcription")
            self._emit("idle")
            return

        self._emit("transcribing")
        threading.Thread(
            target=self._transcribe_worker,
            args=(audio,),
            daemon=True,
        ).start()

    def _get_model(self):
        # Load once, on the first transcription — keeps startup fast and
        # avoids paying the load cost if the user never presses the hotkey.
        with self._model_lock:
            if self._model is None:
                from faster_whisper import WhisperModel
                self._model = WhisperModel(
                    self.model_path,
                    device="cpu",
                    compute_type="int8",
                )
            return self._model

    def _transcribe_worker(self, audio):
        try:
            model = self._get_model()
            segments, _info = model.transcribe(
                audio,
                language="en",
                vad_filter=True,
                beam_size=5,
            )
            text = " ".join(s.text for s in segments).strip()
        except Exception as e:
            print(f"[voice] transcription failed: {e}")
            self._emit("idle")
            return

        self._emit("idle")
        if text and self.on_transcript_ready is not None:
            try:
                self.on_transcript_ready(text)
            except Exception as e:
                print(f"[voice] transcript callback failed: {e}")
