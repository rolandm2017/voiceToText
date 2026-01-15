# voiceToVibe configuration

WHISPER_MODEL = "large-v3"
LANGUAGE = "en"
DEVICE = "cuda"  # or "cpu"
COMPUTE_TYPE = "float16"  # float16 for GPU, int8 for CPU

# Audio settings
SAMPLE_RATE = 16000
CHANNELS = 1

# WhisperX settings (from your working command)
CHUNK_SIZE = 8
BATCH_SIZE = 8
CONDITION_ON_PREVIOUS_TEXT = True

# Paths
OUTPUT_DIR = "./prompts"
TEMP_DIR = "./temp"
LATEST_FILE = "latest.txt"