"""Lazy loaders for heavy optional dependencies (faster API startup, lower idle RAM)."""
from __future__ import annotations

_cv2 = None
_numpy = None
_soundfile = None
_pydub = None
_mediapipe = None
_device = None


def get_cv2():
    global _cv2
    if _cv2 is None:
        import cv2

        _cv2 = cv2
    return _cv2


def get_numpy():
    global _numpy
    if _numpy is None:
        import numpy as np

        _numpy = np
    return _numpy


def get_soundfile():
    global _soundfile
    if _soundfile is None:
        import soundfile as sf

        _soundfile = sf
    return _soundfile


def get_pydub():
    global _pydub
    if _pydub is None:
        from pydub import AudioSegment

        _pydub = AudioSegment
    return _pydub


def get_mediapipe():
    global _mediapipe
    if _mediapipe is None:
        import mediapipe as mp

        _mediapipe = mp
    return _mediapipe


def get_inference_device():
    global _device
    if _device is None:
        from common.GPU_Check import get_device

        _device = get_device()
    return _device
