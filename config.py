# voiceToText configuration

# --- Transcription ---
WHISPER_MODEL = "large-v3"   # any faster-whisper model name, e.g. "medium", "distil-large-v3"
LANGUAGE = "en"
DEVICE = "auto"              # "auto": Metal (MLX) on Apple Silicon, else cuda; falls back to cpu.
                             # Or force "cuda"/"cpu"
BEAM_SIZE = 5                # faster-whisper only; mlx-whisper is greedy-only
MLX_MODEL = None             # Apple Silicon: HF repo override, e.g. "mlx-community/whisper-large-v3-turbo".
                             # None = "mlx-community/whisper-{WHISPER_MODEL}-mlx"

# --- Audio ---
SAMPLE_RATE = 16000          # what VAD and whisper consume; mic is resampled if needed
VAD_FRAME = 512              # samples per VAD window (32 ms @ 16 kHz) — fixed by Silero v5

# --- Segmentation (the "live" feel) ---
SPEECH_START_PROB = 0.50     # VAD prob above this = speech
SPEECH_KEEP_PROB = 0.35      # hysteresis: stay "in speech" above this
PAUSE_MS = 800               # this much silence finalizes a segment
MIN_SPEECH_MS = 300          # segments with less actual speech are dropped (kills "Thank you." hallucinations)
MAX_SEGMENT_S = 30           # force-cut monologues so text keeps appearing
PRE_ROLL_MS = 300            # audio kept from just before speech onset (avoids clipped first syllables)
KEEP_TRAIL_MS = 200          # trailing silence kept on each segment

# --- Output ---
PROMPTS_DIR = "prompts"
LATEST_FILE = "latest.txt"
SEGMENT_JOIN = " "           # how finalized segments are joined in the text box

# --- Paths ---
VAD_MODEL_PATH = "assets/silero_vad.onnx"
VAD_MODEL_URL = (
    "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"
)
