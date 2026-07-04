"""voiceToVibe entry point: python main.py"""

import os
import urllib.request

import config


def ensure_vad_model():
    """The Silero VAD model ships in the repo; fetch it if somehow missing
    (e.g. someone copied the .py files without assets/)."""
    if os.path.exists(config.VAD_MODEL_PATH):
        return
    os.makedirs(os.path.dirname(config.VAD_MODEL_PATH), exist_ok=True)
    print(f"Downloading Silero VAD model to {config.VAD_MODEL_PATH} ...")
    urllib.request.urlretrieve(config.VAD_MODEL_URL, config.VAD_MODEL_PATH)


def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    ensure_vad_model()
    os.makedirs(config.PROMPTS_DIR, exist_ok=True)

    import gui  # imported late so a missing dependency error is readable

    gui.run()


if __name__ == "__main__":
    main()
