"""Speech-to-text providers: OpenRouter Whisper (primary), Amazon Transcribe (fallback), local Whisper (dev)."""
from common.speech.factory import transcribe_audio_file, get_stt_diagnostics

__all__ = ["transcribe_audio_file", "get_stt_diagnostics"]
