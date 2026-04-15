# import wave
# from piper import PiperVoice

# voice = PiperVoice.load(r"C:\Users\neera\Downloads\Piper_my\Piper\en_GB-alan-medium.onnx")
# with wave.open("test1.wav", "wb") as wav_file:
#     voice.synthesize_wav("The rapid growth of artificial intelligence over the past decade has reshaped ", wav_file)

# import io
# import wave
# from piper import PiperVoice

# MODEL_PATH = r"C:\Users\neera\Downloads\Piper_my\Piper\en_GB-alan-medium.onnx"
# voice = PiperVoice.load(MODEL_PATH)

# def synthesize_text_to_wav(text: str, output_path: str = "output.wav"):
#     with wave.open(output_path, "wb") as wav_file:
#         voice.synthesize_wav(text, wav_file)
#     return output_path


import io
import wave
import os
import tempfile
import hashlib
from datetime import datetime
from piper import PiperVoice
from dotenv import load_dotenv

# Load environment variables from backend .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Use environment variable if set, otherwise fall back to relative path
MODEL_PATH = os.getenv("PIPER_MODEL_PATH", os.path.join(os.path.dirname(__file__), "en_US-kusal-medium.onnx"))

# Initialize voice model globally
voice = None

def initialize_voice():
    """Initialize the Piper voice model"""
    global voice
    if voice is None:
        try:
            print(f"[INFO] Loading Piper voice model from: {MODEL_PATH}")
            voice = PiperVoice.load(MODEL_PATH)
            print("[DONE] Piper voice model loaded successfully")
        except Exception as e:
            print(f"[ERROR] Failed to load Piper voice model: {e}")
            raise RuntimeError(f"Voice model initialization failed: {e}")

def synthesize_text_to_wav(text: str, output_path: str = None):
    """Synthesize text to WAV file and return the path"""
    if voice is None:
        initialize_voice()
    
    if not output_path:
        # Create temporary file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        output_path = temp_file.name
        temp_file.close()
    
    try:
        with wave.open(output_path, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        return output_path
    except Exception as e:
        print(f"[ERROR] Text synthesis failed: {e}")
        raise RuntimeError(f"Text synthesis failed: {e}")

def synthesize_text_to_bytes(text: str):
    """Synthesize text to WAV bytes (for direct upload)"""
    if voice is None:
        initialize_voice()
    
    try:
        # Create in-memory WAV file
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            voice.synthesize_wav(text, wav_file)
        
        wav_buffer.seek(0)
        return wav_buffer.getvalue()
    except Exception as e:
        print(f"[ERROR] Text synthesis to bytes failed: {e}")
        raise RuntimeError(f"Text synthesis to bytes failed: {e}")

def generate_filename(text: str, user_id: str = None):
    """Generate unique filename for TTS audio"""
    # Create hash of text for consistent naming
    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    
    if user_id:
        return f"tts_{user_id}_{text_hash}_{timestamp}.wav"
    else:
        return f"tts_{text_hash}_{timestamp}.wav"

# Initialize voice model when module is imported
try:
    initialize_voice()
except Exception as e:
    print(f"[WARNING] Voice model initialization deferred: {e}")