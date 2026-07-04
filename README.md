# voiceToVibe

Local, GPU-powered voice-to-text for prompting AI assistants. Speak into your
mic, watch the transcription appear live as you talk, click **Done**, and the
text is on your clipboard — ready to paste into Claude (or wherever). Your
voice never leaves your machine.

Speaking is much faster than typing. That's the whole pitch.

## How the "live" part works

Whisper models are batch, not streaming. voiceToVibe gets a live feel without
re-transcription hacks: a local VAD (Silero) watches the mic, and every time
you pause naturally (~0.8 s of silence), that chunk of speech is transcribed
with Whisper **large-v3** and appended to the text box. You can always read
back what you've said so far — text is final once it appears, never revised.

## Requirements

- Python 3.10+
- An NVIDIA GPU with ~4 GB+ free VRAM for `large-v3` (8–12 GB cards are
  comfortable). No GPU? It falls back to CPU (`int8`) automatically — slower
  but works.
- An NVIDIA driver. The CUDA runtime libraries themselves (cuBLAS, cuDNN 9)
  can be pip-installed via the `[cuda]` extra below — no CUDA toolkit
  install needed.

PyTorch is **not** required — transcription runs on
[CTranslate2](https://github.com/OpenNMT/CTranslate2) via
[faster-whisper](https://github.com/SYSTRAN/faster-whisper).

## Install & run

```bash
git clone https://github.com/<you>/voiceToVibe
cd voiceToVibe
python -m venv .venv          # or: uv venv
.venv\Scripts\activate        # Windows; source .venv/bin/activate elsewhere
pip install -e ".[cuda]"      # or: uv pip install -e ".[cuda]"
                              # CPU-only machine? plain: pip install -e .
python main.py
```

First launch downloads the `large-v3` weights (~3 GB, one time) and then
loads the model in the background — the window opens immediately and the
Record button enables when the model is ready (~10–15 s on later launches).

## Usage

1. Pick a mic (or leave the system default), click **🎤 Record**, talk.
2. Pause briefly whenever you like — the text of what you just said appears.
   The level meter turns green while it hears speech.
3. Click **⏹ Done**. The text is saved to `prompts/<timestamp>.txt` (and
   `prompts/latest.txt`), and copied to the clipboard unless you untick
   *Autocopy to clipboard*.
4. Paste. Repeat.

The text box is editable — trim your rambles before clicking Done if you
care. **¶ Paragraph** (or `Ctrl+Enter`) starts a new paragraph, so the next
thing you say lands on a fresh line. **✕ Cancel** (or `Ctrl+Shift+D`)
discards the current recording. Audio is never written to disk.

## Configuration

Everything tunable lives in `config.py`: model name (`distil-large-v3` or
`medium` for smaller GPUs), language, pause length that finalizes a segment,
CPU/GPU forcing, etc.

## Credits

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT) — transcription
- [Silero VAD](https://github.com/snakers4/silero-vad) (MIT) — the bundled
  `assets/silero_vad.onnx` voice-activity model
