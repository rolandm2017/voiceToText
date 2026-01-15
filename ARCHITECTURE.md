# Complete Architecture

  voiceToVibe/
  ├── main.py              # Entry point, launches GUI
  ├── gui.py               # Tkinter window
  ├── recorder.py          # Mic recording (sounddevice → .wav)
  ├── transcriber.py       # WhisperX wrapper
  ├── config.py            # Settings (model size, language, output path)
  ├── prompts/             # Output folder
  │   └── latest.txt       # Most recent transcription
  └── temp/                # Temp audio files (auto-cleaned)

##  Flow Diagram

#### Version 1

  ┌──────────────────────────────────────────────────────────────┐
  │                    voiceToVibe GUI                           │
  ├──────────────────────────────────────────────────────────────┤
  │                                                              │
  │   [ 🎤 Record ]    [ ⏹ Stop & Transcribe ]                  │
  │                                                              │
  │   Status: Idle / Recording... / Transcribing (chunk 2/4)... │
  │                                                              │
  │   ┌────────────────────────────────────────────────────────┐ │
  │   │                                                        │ │
  │   │  Your transcribed text appears here.                   │ │
  │   │  It's automatically copied to clipboard.               │ │
  │   │                                                        │ │
  │   └────────────────────────────────────────────────────────┘ │
  │                                                              │
  │   [📋 Copy Again]   Saved to: prompts/latest.txt            │
  └──────────────────────────────────────────────────────────────┘

#### Version 2
    ┌──────────────────────────────────────────────────────────────┐
  │  Input: [ (System Default)              ▾ ] [↻]             │
  ├──────────────────────────────────────────────────────────────┤
  │                                                              │
  │       [ 🎤 Record ]    [ ⏹ Stop & Transcribe ]              │
  │                                                              │
  │   Status: Idle                                               │
  │                                                              │
  │   ┌────────────────────────────────────────────────────────┐ │
  │   │ Transcribed text appears here                          │ │
  │   └────────────────────────────────────────────────────────┘ │
  │                                                              │
  │                  [📋 Copy to Clipboard]                      │
  │            Saves to: prompts/latest.txt                      │
  └──────────────────────────────────────────────────────────────┘

  What Happens Under the Hood

  User clicks Record
         │
         ▼
  ┌─────────────────┐
  │ sounddevice     │ ──► temp/recording.wav (16kHz mono)
  │ records mic     │
  └─────────────────┘
         │
  User clicks Stop
         │
         ▼
  ┌─────────────────┐
  │ WhisperX loads  │  (first time: ~10-15s, cached after)
  │ model if needed │
  └─────────────────┘
         │
         ▼
  ┌─────────────────┐
  │ WhisperX        │ ──► chunks processed (~5s per 30s audio)
  │ transcribes     │
  └─────────────────┘
         │
         ▼
  ┌─────────────────┐
  │ Output:         │
  │ • GUI text box  │
  │ • Clipboard     │
  │ • prompts/      │
  │   latest.txt    │
  └─────────────────┘

  Dependencies (Windows/pip)

  whisperx          # You already have this
  sounddevice       # Cross-platform mic recording
  scipy             # For saving .wav files
  tkinter           # Built into Python on Windows
  pyperclip         # Clipboard access (or win32clipboard)

  Optional Enhancements (later)

  - Keep model loaded - Skip the 10-15s load time between recordings
  - Hotkey support - Global hotkey to start/stop without focusing the window
  - Auto-punctuation - WhisperX handles this decently
  - History - Save timestamped transcriptions, not just latest.txt
