# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

voiceToVibe is a local voice-to-text tool for prompting AI assistants by
voice. The user records from a mic, speech is transcribed *live* (segment by
segment at natural pauses) using faster-whisper large-v3 on the local GPU,
and on Done the text is saved to `prompts/` and autocopied to the clipboard.
No audio is ever written to disk; nothing leaves the machine.

## Running

```bash
python main.py                 # the app
python audio.py                # 10s mic + VAD smoke test (no GUI, no model)
python transcriber.py x.wav    # model-load + transcription smoke test
```

The venv is Windows-side (`.venv/Scripts/python.exe`); Claude Code runs in
WSL and cannot use the mic/GUI/CUDA — ask the user to run tests.

## Dependencies

`pip install -e .` (see pyproject.toml): sounddevice, faster-whisper,
onnxruntime, numpy, pyperclip. No PyTorch. CUDA/cuDNN runtime setup is the
user's responsibility.

## Architecture (see ARCHITECTURE.md for the full picture)

- `main.py` — entry point
- `gui.py` — Tkinter app; **all state lives here and is mutated only on the
  GUI thread**, fed by an event queue drained via `root.after`
- `audio.py` — mic capture (sounddevice) + Silero VAD segmentation; emits
  in-memory float32 segments at pause boundaries (worker thread)
- `transcriber.py` — faster-whisper wrapper; background model load, job
  queue (worker thread)
- `config.py` — all tunables (model, device, pause thresholds, paths)
- `assets/silero_vad.onnx` — vendored Silero VAD v5 model (MIT)

Key invariants to preserve when editing:
- Worker threads never touch Tk; they only `emit(event_tuple)`.
- The PortAudio callback only enqueues samples.
- Cancellation is by session id — never by interrupting workers.
- `AudioEngine.stop()` must keep its guarantee: the flushed final segment is
  in the event queue before it returns.

## Configuration

Edit `config.py`: `WHISPER_MODEL` (large-v3 default), `DEVICE`
("auto"/"cuda"/"cpu"), `PAUSE_MS` (silence that finalizes a segment),
`MAX_SEGMENT_S` (monologue force-cut), VAD thresholds, paths.
