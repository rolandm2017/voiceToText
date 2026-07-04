"""Mic capture + Silero VAD segmentation.

Audio never touches disk. The flow:

    sounddevice callback -> raw frame queue -> worker thread:
        resample to 16 kHz if needed
        slice into 512-sample VAD windows
        run Silero VAD, group speech into segments split at pauses
        emit ("segment", float32 ndarray) / ("level", rms, is_speech) events

Events are posted via the `emit` callable given to AudioEngine.start()
(the GUI passes its event queue's put method).
"""

import queue
import threading

import numpy as np
import onnxruntime
import sounddevice as sd

import config

FRAME = config.VAD_FRAME
FRAME_MS = FRAME * 1000 // config.SAMPLE_RATE  # 32


class SileroVAD:
    """Minimal onnxruntime wrapper for the Silero VAD v5 model (16 kHz)."""

    def __init__(self, model_path: str):
        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        self.session = onnxruntime.InferenceSession(
            model_path, sess_options=opts, providers=["CPUExecutionProvider"]
        )
        self.reset()

    def reset(self):
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)

    def __call__(self, chunk: np.ndarray) -> float:
        """chunk: float32 array of exactly FRAME samples. Returns speech probability."""
        x = np.concatenate([self._context, chunk.reshape(1, -1)], axis=1).astype(np.float32)
        out, state = self.session.run(
            None, {"input": x, "state": self._state, "sr": np.array(16000, dtype=np.int64)}
        )
        self._state = state
        self._context = x[:, -64:]
        return float(out[0][0])


class Resampler:
    """Chunk-wise linear resampler with sample carryover between chunks."""

    def __init__(self, src_rate: int, dst_rate: int):
        self.ratio = src_rate / dst_rate
        self._buf = np.zeros(0, dtype=np.float32)
        self._pos = 0.0

    def process(self, chunk: np.ndarray) -> np.ndarray:
        self._buf = np.concatenate([self._buf, chunk])
        max_pos = len(self._buf) - 1
        if self._pos > max_pos:
            return np.zeros(0, dtype=np.float32)
        positions = self._pos + np.arange(int((max_pos - self._pos) // self.ratio) + 1) * self.ratio
        out = np.interp(positions, np.arange(len(self._buf)), self._buf).astype(np.float32)
        self._pos = positions[-1] + self.ratio
        consumed = min(int(self._pos), len(self._buf))  # samples we'll never need again
        self._buf = self._buf[consumed:]
        self._pos -= consumed
        return out


class _Segmenter:
    """VAD state machine: frames in, finished speech segments out."""

    def __init__(self, vad: SileroVAD, emit):
        self.vad = vad
        self.emit = emit
        self.pre_roll_n = max(1, config.PRE_ROLL_MS // FRAME_MS)
        self.pause_frames = max(1, config.PAUSE_MS // FRAME_MS)
        self.keep_trail = max(0, config.KEEP_TRAIL_MS // FRAME_MS)
        self.min_speech_frames = max(1, config.MIN_SPEECH_MS // FRAME_MS)
        self.max_frames = config.MAX_SEGMENT_S * 1000 // FRAME_MS
        self.reset()

    def reset(self):
        self.vad.reset()
        self.pre_roll = []
        self.segment = []
        self.in_speech = False
        self.speech_frames = 0
        self.silence_run = 0
        self._level_tick = 0

    def feed(self, frame: np.ndarray):
        prob = self.vad(frame)
        is_speech = prob >= config.SPEECH_START_PROB

        self._level_tick += 1
        if self._level_tick % 2 == 0:
            rms = float(np.sqrt(np.mean(frame**2)))
            self.emit(("level", rms, is_speech))

        if not self.in_speech:
            self.pre_roll.append(frame)
            if len(self.pre_roll) > self.pre_roll_n:
                self.pre_roll.pop(0)
            if is_speech:
                self.in_speech = True
                self.segment = list(self.pre_roll)
                self.pre_roll = []
                self.speech_frames = 1
                self.silence_run = 0
            return

        self.segment.append(frame)
        if prob >= config.SPEECH_KEEP_PROB:
            self.silence_run = 0
            if is_speech:
                self.speech_frames += 1
        else:
            self.silence_run += 1

        if self.silence_run >= self.pause_frames:
            trim = self.silence_run - self.keep_trail
            frames = self.segment[:-trim] if trim > 0 else self.segment
            self._finish(frames)
            # seed the next pre-roll with the audio we trimmed off
            self.pre_roll = self.segment[-self.pre_roll_n:]
            self.segment = []
            self.in_speech = False
        elif len(self.segment) >= self.max_frames:
            self._finish(self.segment)  # force-cut a monologue; stay in speech
            self.segment = []
            self.speech_frames = 1
            self.silence_run = 0

    def flush(self):
        """Called when recording stops mid-speech."""
        if self.in_speech:
            self._finish(self.segment)
        self.segment = []
        self.in_speech = False

    def _finish(self, frames):
        if self.speech_frames >= self.min_speech_frames and frames:
            self.emit(("segment", np.concatenate(frames)))
        self.speech_frames = 0


class AudioEngine:
    """Owns the input stream and the VAD worker thread."""

    def __init__(self, vad_model_path: str):
        self.vad = SileroVAD(vad_model_path)
        self._raw: queue.Queue = queue.Queue()
        self._worker = None
        self._stream = None
        self._flush_on_stop = True

    def start(self, device, emit):
        """device: sounddevice index or None for system default.
        emit: callable taking one event tuple; called from the worker thread."""
        self._raw = queue.Queue()
        self._segmenter = _Segmenter(self.vad, emit)
        self._emit = emit
        self._flush_on_stop = True

        def callback(indata, n_frames, time_info, status):
            self._raw.put(indata[:, 0].copy())

        # Prefer capturing at 16 kHz directly; fall back to the device's
        # native rate + our own resampling if the backend refuses.
        try:
            self._stream = sd.InputStream(
                device=device, samplerate=config.SAMPLE_RATE, channels=1,
                dtype="float32", blocksize=FRAME, callback=callback,
            )
            src_rate = config.SAMPLE_RATE
        except sd.PortAudioError:
            info = sd.query_devices(device, "input")
            src_rate = int(info["default_samplerate"])
            self._stream = sd.InputStream(
                device=device, samplerate=src_rate, channels=1,
                dtype="float32", callback=callback,
            )
        self._resampler = None if src_rate == config.SAMPLE_RATE else Resampler(
            src_rate, config.SAMPLE_RATE
        )
        self._stream.start()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def stop(self, flush: bool = True):
        """Stop capture. Blocks until the worker has drained; guarantees the
        final ("segment", ...) event (if any) is emitted before returning."""
        self._flush_on_stop = flush
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._raw.put(None)  # sentinel
        if self._worker is not None:
            self._worker.join(timeout=5)
            self._worker = None

    def _run(self):
        pending = np.zeros(0, dtype=np.float32)
        try:
            while True:
                chunk = self._raw.get()
                if chunk is None:
                    break
                if self._resampler is not None:
                    chunk = self._resampler.process(chunk)
                pending = np.concatenate([pending, chunk])
                while len(pending) >= FRAME:
                    self._segmenter.feed(pending[:FRAME])
                    pending = pending[FRAME:]
            if self._flush_on_stop:
                self._segmenter.flush()
        except Exception as e:  # surface worker crashes instead of dying silently
            self._emit(("audio_error", f"{type(e).__name__}: {e}"))


def list_input_devices():
    """Returns [(index_or_None, label), ...] with system default first.
    Prefers the WASAPI host API on Windows to avoid MME's duplicated,
    name-truncated entries."""
    devices = [(None, "(System Default)")]
    apis = sd.query_hostapis()
    preferred = next((i for i, a in enumerate(apis) if "WASAPI" in a["name"]), None)
    for idx, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] <= 0:
            continue
        if preferred is not None and dev["hostapi"] != preferred:
            continue
        devices.append((idx, dev["name"]))
    return devices


def refresh_devices():
    """Force PortAudio to re-enumerate (picks up newly plugged-in mics)."""
    sd._terminate()
    sd._initialize()


if __name__ == "__main__":
    # Headless smoke test: 10 seconds of mic + VAD, no GUI, no whisper.
    import time

    print("Recording 10s from default mic. Talk, pause, talk...")
    engine = AudioEngine(config.VAD_MODEL_PATH)

    def emit(event):
        if event[0] == "segment":
            print(f"  -> segment finalized: {len(event[1]) / config.SAMPLE_RATE:.2f}s of audio")
        elif event[0] == "level" and event[2]:
            print(".", end="", flush=True)
        elif event[0] == "audio_error":
            print("AUDIO ERROR:", event[1])

    engine.start(None, emit)
    time.sleep(10)
    engine.stop()
    print("\nDone. If you saw dots while speaking and 'segment finalized' after pauses, VAD works.")
