# setup

To Install Dependencies

```bash
pip install sounddevice scipy

(You already have whisperx, torch, etc.)
```

#  CLI Alternative

If the Python API gives you trouble, swap transcriber.py for a subprocess call:

```python
import subprocess
import os
import config

class Transcriber:
    def transcribe(self, audio_path: str) -> str:
        output_dir = config.TEMP_DIR

        cmd = [
            "whisperx", audio_path,
            "--language", config.LANGUAGE,
            "--model", config.WHISPER_MODEL,
            "--chunk_size", str(config.CHUNK_SIZE),
            "--batch_size", str(config.BATCH_SIZE),
            "--condition_on_previous_text", "True",
            "--output_dir", output_dir,
            "--output_format", "txt"
        ]

        subprocess.run(cmd, check=True)

        # WhisperX outputs: {filename}.txt
        base = os.path.splitext(os.path.basename(audio_path))[0]
        txt_path = os.path.join(output_dir, f"{base}.txt")

        with open(txt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
```