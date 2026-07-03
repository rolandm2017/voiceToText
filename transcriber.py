# transcriber.py

import numpy as np
import config

class Transcriber:
    def __init__(self):
        self.model = None
        self.is_loading = False

    @property
    def is_loaded(self) -> bool:
        return self.model is not None

    def load_model(self):
        if self.model is None:
            self.is_loading = True
            import whisperx
            try:
                self.model = whisperx.load_model(
                    config.WHISPER_MODEL,
                    config.DEVICE,
                    compute_type=config.COMPUTE_TYPE
                )
            except Exception as primary_error:
                # Common failure mode on Windows: CUDA requested but unavailable.
                if config.DEVICE == "cuda":
                    self.model = whisperx.load_model(
                        config.WHISPER_MODEL,
                        "cpu",
                        compute_type="int8"
                    )
                else:
                    raise primary_error
            finally:
                self.is_loading = False
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

    def transcribe_array(self, audio: np.ndarray) -> str:
        """Transcribe directly from a numpy array of audio samples.

        Args:
            audio: Float32 numpy array of audio samples at 16kHz
        """
        if not self.is_loaded:
            return ""

        # Ensure correct dtype and shape
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        if audio.ndim > 1:
            audio = audio[:, 0]

        result = self.model.transcribe(
            audio,
            language=config.LANGUAGE,
            chunk_size=config.CHUNK_SIZE,
            batch_size=config.BATCH_SIZE,
            condition_on_previous_text=config.CONDITION_ON_PREVIOUS_TEXT
        )

        segments = result.get("segments", [])
        text = " ".join(seg["text"].strip() for seg in segments)

        return text
