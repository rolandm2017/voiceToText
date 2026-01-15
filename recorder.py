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
        self.device_id = None  # None = system default

    @staticmethod
    def get_input_devices() -> list[tuple[int, str]]:
        """Returns list of (device_id, device_name) for input devices."""
        devices = sd.query_devices()
        input_devices = []
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                input_devices.append((i, dev['name']))
        return input_devices

    def set_device(self, device_id: int | None):
        """Set the input device. None = system default."""
        self.device_id = device_id

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
            device=self.device_id,  # <-- uses selected device
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

        audio = np.concatenate(self.audio_data, axis=0)
        audio_int16 = (audio * 32767).astype(np.int16)

        if audio_int16.ndim > 1:
            audio_int16 = audio_int16[:, 0]

        os.makedirs(config.TEMP_DIR, exist_ok=True)
        wav_path = os.path.join(config.TEMP_DIR, "recording.wav")
        wav.write(wav_path, config.SAMPLE_RATE, audio_int16)

        return wav_path