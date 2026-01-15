# recorder.py

import sounddevice as sd
import scipy.io.wavfile as wav
import numpy as np
import os
import config

class Recorder:
    def __init__(self):
        self.audio_data = []
        self.is_recording = False
        self.stream = None

    def _callback(self, indata, frames, time, status):
        if status:
            print(f"Recording status: {status}")
        if self.is_recording:
            self.audio_data.append(indata.copy())

    def start(self):
        self.audio_data = []
        self.is_recording = True
        self.stream = sd.InputStream(
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype='float32',
            callback=self._callback
        )
        self.stream.start()

    def stop(self) -> str:
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_data:
            return None

        # Concatenate all chunks
        audio = np.concatenate(self.audio_data, axis=0)

        # Convert float32 [-1, 1] to int16
        audio_int16 = (audio * 32767).astype(np.int16)

        # Flatten if stereo (shouldn't be, but just in case)
        if audio_int16.ndim > 1:
            audio_int16 = audio_int16[:, 0]

        # Save to temp file
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        wav_path = os.path.join(config.TEMP_DIR, "recording.wav")
        wav.write(wav_path, config.SAMPLE_RATE, audio_int16)

        return wav_path
