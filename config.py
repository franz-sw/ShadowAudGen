import os
from dotenv import load_dotenv

load_dotenv()

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# API Configuration
XAI_API_KEY = os.getenv("XAI_API_KEY")
if not XAI_API_KEY:
    print("Warning: XAI_API_KEY not set in .env file")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    print("Warning: ELEVENLABS_API_KEY not set in .env file")

LLM_MODEL = "grok-4.20-0309-reasoning"
LLM_MODEL_NO_REASONING = "grok-4.20-0309-non-reasoning"
TEMPERATURE = 0.7
MAX_TOKENS = 800

ELEVENLABS_VOICE_ID = "polm59PrdXp5lKpce2EG"  # Main voice for answers
# QUESTION_VOICE_ID = "xjlfQQ3ynqiEyRpArrT8"   # Vera - Female voice for questions
# QUESTION_VOICE_ID = "RGymW84CSmfVugnA5tvA"   # Roberta - Female voice for questions
QUESTION_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"   # Sarah - Female voice for questions
# QUESTION_VOICE_ID = "XrExE9yKIg1WjnnlVkGX"   # Matilda - Female voice for questions
# ELEVENLABS_MODEL_ID = "eleven_turbo_v2_5"
ELEVENLABS_MODEL_ID = "eleven_flash_v2_5"

# Whisper Model Configuration
WHISPER_MODEL_STORAGE = "D:/ai/models/whisper"
# WHISPER_MODEL_NAME = "turbo"
WHISPER_MODEL_NAME = "large-v3"

DB_PATH = os.path.join(BASE_DIR, "shadowing.db")
INPUT_DIR = os.path.join(BASE_DIR, "input")
DEFAULT_JSON = os.path.join(INPUT_DIR, "shadowing_source_input.json")

MAX_WORKERS = 4
MAX_LLM_WORKERS = 4
RETRY_ATTEMPTS = 3
RATE_LIMIT_DELAY = 1.0

# Global segment break (applied on top of multiplier gap)
SEGMENT_BREAK_MS = 500

# Castopod Configuration
CASTOPOD_HOST = os.getenv("CASTOPOD_HOST")
CASTOPOD_PODCAST_ID = os.getenv("CASTOPOD_PODCAST_ID")
CASTOPOD_USER_ID = os.getenv("CASTOPOD_USER_ID")
CASTOPOD_AUTH_USERNAME = os.getenv("CASTOPOD_AUTH_USERNAME")
CASTOPOD_AUTH_PASSWORD = os.getenv("CASTOPOD_AUTH_PASSWORD")

SHADOWING_SOURCES_BASE_URL = os.getenv("SHADOWING_SOURCES_BASE_URL")

AUDIO_FILE_PREFIX = "[MK1]"

# Language settings
DEFAULT_LANGUAGE = "hu"
