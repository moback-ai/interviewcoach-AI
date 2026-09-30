from __future__ import annotations

from common.runtime_config import optional_env

_whisper_model = None


def _get_whisper():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model
    import faster_whisper
    from common.lazy_deps import get_inference_device

    model_size = optional_env("WHISPER_MODEL", "base.en")
    inference_device = get_inference_device()
    device = "cpu" if inference_device == "mps" else inference_device
    _whisper_model = faster_whisper.WhisperModel(model_size, device=device)
    return _whisper_model


def transcribe_local_whisper(wav_path: str) -> dict:
    try:
        model = _get_whisper()
        beam_size = max(1, int(optional_env("WHISPER_BEAM_SIZE", "1")))
        whisper_lang = optional_env("WHISPER_LANGUAGE", "en")
        segments, _info = model.transcribe(
            wav_path,
            beam_size=beam_size,
            language=whisper_lang,
            task="transcribe",
        )
        text = " ".join(s.text for s in segments).strip()
        return {"success": True, "transcription": text, "provider": "local_whisper"}
    except Exception as exc:
        return {"success": False, "error": str(exc), "provider": "local_whisper"}


def local_whisper_diagnostics() -> dict:
    try:
        _get_whisper()
        return {"provider": "local_whisper", "ready": True, "configured": True}
    except Exception as exc:
        return {
            "provider": "local_whisper",
            "ready": False,
            "configured": True,
            "error": str(exc),
        }
