"""Whisper wrapper (faster-whisper on CUDA/CPU, mlx-whisper on Apple Silicon): background model load + segment worker thread.

Results are posted as event tuples via the `emit` callable:
    ("model_ready", "large-v3 on cuda (float16)")
    ("model_error", message)
    ("segment_text", session_id, text)
"""

import os
import platform
import queue
import sys
import threading
from pathlib import Path

import numpy as np

import config


def _add_nvidia_dll_dirs():
    """On Windows, the pip-installed nvidia-cublas-cu12 / nvidia-cudnn-cu12
    wheels drop their DLLs in site-packages/nvidia/*/bin, which is not on the
    DLL search path. Register those dirs so CTranslate2 can find them."""
    if sys.platform != "win32":
        return
    root = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
    if root.is_dir():
        for bin_dir in root.glob("*/bin"):
            os.add_dll_directory(str(bin_dir))


def _use_mlx():
    """Apple Silicon: run Whisper on the Metal GPU via MLX (faster-whisper's
    CTranslate2 backend has no Metal support, so it would be CPU-only)."""
    if config.DEVICE == "cpu":
        return False
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _mlx_repo():
    return config.MLX_MODEL or f"mlx-community/whisper-{config.WHISPER_MODEL}-mlx"


class _MlxModel:
    """Adapts mlx_whisper to the one-call interface the worker loop uses."""

    def __init__(self):
        import mlx_whisper  # slow import, keep off the GUI thread
        self._mlx_whisper = mlx_whisper
        self.repo = _mlx_repo()

    def transcribe(self, audio, prompt_tail=None):
        # mlx_whisper has no beam search; greedy decoding is its only mode
        result = self._mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self.repo,
            language=config.LANGUAGE,
            initial_prompt=prompt_tail or None,
            condition_on_previous_text=False,
            without_timestamps=True,
        )
        return result["text"].strip()


class _FasterWhisperModel:
    def __init__(self, device, compute_type):
        from faster_whisper import WhisperModel  # slow import, keep off the GUI thread
        self._model = WhisperModel(config.WHISPER_MODEL, device=device,
                                   compute_type=compute_type)

    def transcribe(self, audio, prompt_tail=None):
        segments, _info = self._model.transcribe(
            audio,
            language=config.LANGUAGE,
            beam_size=config.BEAM_SIZE,
            initial_prompt=prompt_tail or None,
            vad_filter=False,  # VAD already happened upstream
            without_timestamps=True,
        )
        return " ".join(s.text.strip() for s in segments).strip()


class Transcriber:
    def __init__(self, emit):
        self.emit = emit
        self.model = None
        self._jobs: queue.Queue = queue.Queue()
        threading.Thread(target=self._load_then_work, daemon=True).start()

    def submit(self, audio, session_id: int, prompt_tail: str | None):
        """audio: float32 ndarray @ 16 kHz. Called from the GUI thread."""
        self._jobs.put((audio, session_id, prompt_tail))

    # --- worker thread ---

    def _load_then_work(self):
        _add_nvidia_dll_dirs()

        attempts = []
        if _use_mlx():
            attempts.append(("metal", "mlx"))
        elif config.DEVICE in ("auto", "cuda"):
            attempts.append(("cuda", "float16"))
        if config.DEVICE in ("auto", "cpu"):
            attempts.append(("cpu", "int8"))

        error = None
        for device, compute_type in attempts:
            try:
                if device == "metal":
                    self.model = _MlxModel()
                else:
                    self.model = _FasterWhisperModel(device, compute_type)
                # force weight load / GPU init now, not on the first real segment
                self.model.transcribe(np.zeros(1600, dtype=np.float32))
                self.emit(("model_ready", f"{config.WHISPER_MODEL} on {device} ({compute_type})"))
                break
            except Exception as e:
                error = e
                self.model = None
        if self.model is None:
            self.emit(("model_error", f"Could not load model: {error}"))
            return

        while True:
            audio, session_id, prompt_tail = self._jobs.get()
            try:
                text = self.model.transcribe(audio, prompt_tail)
            except Exception as e:
                text = ""
                self.emit(("model_error", f"Transcription failed: {e}"))
            self.emit(("segment_text", session_id, text))

if __name__ == "__main__":
    # Smoke test: python transcriber.py [path/to/16khz-mono.wav]
    import sys
    import time
    import wave

    events: queue.Queue = queue.Queue()
    t = Transcriber(events.put)
    print("Loading model...")
    while True:
        ev = events.get()
        print(ev[0], ev[1] if len(ev) > 1 else "")
        if ev[0] == "model_error":
            sys.exit(1)
        if ev[0] == "model_ready":
            break
    if len(sys.argv) > 1:
        with wave.open(sys.argv[1], "rb") as w:
            assert w.getframerate() == 16000 and w.getnchannels() == 1, "need 16kHz mono wav"
            audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            audio = audio.astype(np.float32) / 32768.0
        start = time.time()
        t.submit(audio, 0, None)
        ev = events.get()
        print(f"[{time.time() - start:.1f}s] {ev[2]}")
