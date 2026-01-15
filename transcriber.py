# transcriber.py

import config

class Transcriber:
    def __init__(self):
        self.model = None

    def load_model(self):
        if self.model is None:
            import whisperx
            self.model = whisperx.load_model(
                config.WHISPER_MODEL,
                config.DEVICE,
                compute_type=config.COMPUTE_TYPE
            )
        return self.model

    def transcribe(self, audio_path: str) -> str:
        import whisperx

        model = self.load_model()
        audio = whisperx.load_audio(audio_path)

        result = model.transcribe(
            audio,
            language=config.LANGUAGE,
            chunk_size=config.CHUNK_SIZE,
            batch_size=config.BATCH_SIZE,
            condition_on_previous_text=config.CONDITION_ON_PREVIOUS_TEXT
        )

        # Extract text from segments
        segments = result.get("segments", [])
        text = " ".join(seg["text"].strip() for seg in segments)

        return text