# Architecture

```
voiceToVibe/
├── main.py            # entry point: dirs, VAD model check, launch GUI
├── gui.py             # Tkinter app — ALL state lives here, on the GUI thread
├── audio.py           # mic capture + Silero VAD segmenter (worker thread)
├── transcriber.py     # faster-whisper wrapper (worker thread)
├── config.py          # every tunable
├── assets/
│   └── silero_vad.onnx  # vendored Silero VAD v5 (MIT)
└── prompts/           # output: <timestamp>.txt + latest.txt (gitignored)
```

## Pipeline

```
mic ── sounddevice InputStream (float32; 16 kHz, or native rate + resample)
        │  PortAudio callback thread: just queue.put, nothing else
        ▼
audio.py worker thread
        │  slice into 512-sample (32 ms) windows
        │  Silero VAD prob per window (onnxruntime, CPU, ~negligible)
        │  state machine: speech onset (with 300 ms pre-roll)
        │    → pause ≥ 800 ms finalizes a segment
        │    → 30 s without a pause force-cuts one (monologue guard)
        │    → < 300 ms of speech is dropped (anti-hallucination)
        ▼
("segment", ndarray) event ──► GUI event queue
        │  GUI thread forwards to transcriber, pending += 1
        ▼
transcriber.py worker thread
        │  faster-whisper large-v3 (cuda/float16, fallback cpu/int8)
        │  initial_prompt = last 200 chars of the box, for continuity
        ▼
("segment_text", session, text) ──► GUI event queue
        │  append to text box, pending -= 1
        ▼
Done clicked: stop stream, flush tail segment, wait pending == 0, then
write prompts/<timestamp>.txt + latest.txt and copy to clipboard.
```

## Threading model

Three threads, one rule: **all state mutation happens on the GUI thread.**

- **PortAudio callback**: copies samples into a `queue.Queue`. Nothing else.
- **Audio worker** (`audio.py`): VAD + segmentation; emits event tuples.
- **Transcriber worker** (`transcriber.py`): model load at startup, then a
  job loop; emits event tuples.
- **GUI thread**: `root.after(40, _poll)` drains the event queue.

Cancellation uses a session counter: each Record bumps `session`; segment
results are tagged with it and stale ones are dropped on arrival. So Cancel
never has to interrupt an in-flight GPU call — it just orphans the result.

`AudioEngine.stop()` joins its worker, which guarantees the final flushed
segment is already in the event queue when stop() returns — the Done handler
drains events synchronously right after, so `pending` is accurate before the
"can I finalize yet?" check.

## Why no audio files?

Segments go from mic to VAD to whisper entirely as in-memory float32 arrays.
Nothing to clean up, nothing to leak.

## Smoke tests

- `python audio.py` — 10 s mic + VAD test, prints finalized segments. No GUI,
  no model download.
- `python transcriber.py some-16khz-mono.wav` — model load + one transcription.
