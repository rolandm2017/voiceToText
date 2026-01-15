# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

voiceToVibe is a voice-to-text transcription tool with a Tkinter GUI. The goal is to enable prompting AI assistants (like Claude) with voice instead of keyboard. Users record audio via microphone, the audio is transcribed using WhisperX, and the text is automatically copied to clipboard.

## Running the Application

```bash
python main.py
```

## Dependencies

Requires a virtual environment with WhisperX and CUDA support:
```bash
pip install sounddevice scipy whisperx
```

Note: tkinter is built into Python on Windows. WhisperX requires PyTorch with CUDA for GPU acceleration.

## Architecture

The application follows a simple flow: Record → Save WAV → Transcribe → Output to clipboard/file.

**Core modules:**
- `main.py` - Entry point, creates directories and launches GUI
- `gui.py` - Tkinter interface with VoiceToVibeApp class handling UI state and threading
- `recorder.py` - Microphone capture using sounddevice, saves to temp/recording.wav
- `transcriber.py` - WhisperX wrapper with lazy model loading (model stays cached after first load)
- `config.py` - All settings: model size, device (cuda/cpu), audio params, paths

**Data flow:**
1. sounddevice captures audio at 16kHz mono
2. Audio saved as WAV to `temp/` directory
3. WhisperX transcribes (first run loads model ~10-15s, subsequent runs use cache)
4. Output goes to: GUI text box, clipboard, and `prompts/latest.txt`

**Threading:** Transcription runs in a daemon thread to keep UI responsive. Results are passed back via `root.after()`.

## Configuration

Edit `config.py` to change:
- `WHISPER_MODEL` - Model size (default: "large-v3")
- `DEVICE` - "cuda" or "cpu"
- `COMPUTE_TYPE` - "float16" for GPU, "int8" for CPU
- `CHUNK_SIZE` / `BATCH_SIZE` - WhisperX processing parameters
