# what is the goal?

To prompt AI assistants with my voice instead of my keyboard, using my own
GPU, without sending audio to anyone.

Press **Record**, talk, read the live transcription as it appears (so I can
remember what the hell I've already covered), press **Done**, paste from the
clipboard into Claude Code or the web UI.

Status: built (2026-07). See README.md and ARCHITECTURE.md.

Explicitly out of scope, by choice:
- prebuilt binaries / installers (users can handle a venv)
- handling CUDA/driver installation
- global hotkeys, auto-punctuation cleanup, streaming ASR models
