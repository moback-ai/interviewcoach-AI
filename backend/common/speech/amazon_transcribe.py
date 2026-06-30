from __future__ import annotations

import os
import time
import uuid

from common.runtime_config import optional_env


def _boto3():
    import boto3

    return boto3


def _region() -> str:
    return optional_env("TRANSCRIBE_REGION", optional_env("AWS_REGION", "ap-south-1"))


def _bucket() -> str:
    return optional_env("STT_S3_BUCKET", optional_env("S3_BUCKET", "")).strip()


def transcribe_amazon(audio_path: str) -> dict:
    bucket = _bucket()
    if not bucket:
        return {
            "success": False,
            "error": "STT_S3_BUCKET or S3_BUCKET required for Amazon Transcribe fallback",
            "provider": "amazon",
        }

    region = _region()
    boto3 = _boto3()
    s3 = boto3.client("s3", region_name=region)
    transcribe = boto3.client("transcribe", region_name=region)
    job_name = f"ic-stt-{uuid.uuid4().hex[:16]}"
    ext = os.path.splitext(audio_path)[1].lstrip(".") or "wav"
    key = f"stt-temp/{job_name}.{ext}"
    media_uri = f"s3://{bucket}/{key}"

    try:
        s3.upload_file(audio_path, bucket, key)
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": media_uri},
            MediaFormat=ext if ext in {"mp3", "mp4", "wav", "flac", "ogg", "amr", "webm"} else "wav",
            LanguageCode=optional_env("TRANSCRIBE_LANGUAGE_CODE", "en-US"),
        )
    except Exception as exc:
        return {"success": False, "error": str(exc), "provider": "amazon"}

    deadline = time.time() + int(optional_env("TRANSCRIBE_JOB_TIMEOUT_SECONDS", "90"))
    failure_reason = ""
    transcript_uri = ""
    while time.time() < deadline:
        try:
            job = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            status = job["TranscriptionJob"]["TranscriptionJobStatus"]
            if status == "COMPLETED":
                transcript_uri = job["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
                break
            if status == "FAILED":
                failure_reason = job["TranscriptionJob"].get("FailureReason", "Transcription failed")
                break
        except Exception as exc:
            failure_reason = str(exc)
            break
        time.sleep(1.5)

    try:
        transcribe.delete_transcription_job(TranscriptionJobName=job_name)
    except Exception:
        pass
    try:
        s3.delete_object(Bucket=bucket, Key=key)
    except Exception:
        pass

    if failure_reason:
        return {"success": False, "error": failure_reason, "provider": "amazon"}
    if not transcript_uri:
        return {"success": False, "error": "Amazon Transcribe timed out", "provider": "amazon"}

    import requests as http_requests

    try:
        payload = http_requests.get(transcript_uri, timeout=30).json()
        text = (
            payload.get("results", {})
            .get("transcripts", [{}])[0]
            .get("transcript", "")
            .strip()
        )
    except Exception as exc:
        return {"success": False, "error": str(exc), "provider": "amazon"}

    return {"success": True, "transcription": text, "provider": "amazon"}


def amazon_diagnostics() -> dict:
    info = {
        "provider": "amazon",
        "region": _region(),
        "bucket": _bucket(),
        "configured": bool(_bucket()),
        "ready": bool(_bucket()),
    }
    if not info["configured"]:
        info["error"] = "STT_S3_BUCKET not set"
    return info
