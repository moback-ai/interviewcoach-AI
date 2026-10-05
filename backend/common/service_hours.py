"""Service window: 10:00–20:00 IST (configurable)."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from common.runtime_config import optional_env

DEFAULT_TZ = "Asia/Kolkata"
DEFAULT_START = "10:00"
DEFAULT_END = "19:00"

def _parse_hhmm(value: str, fallback: str) -> tuple[int, int]:
    raw = (value or fallback).strip()
    try:
        hour, minute = raw.split(":", 1)
        return int(hour), int(minute)
    except (TypeError, ValueError):
        fb_hour, fb_minute = fallback.split(":", 1)
        return int(fb_hour), int(fb_minute)

def _format_display_time(hour: int, minute: int) -> str:
    period = "AM" if hour < 12 else "PM"
    hour12 = hour % 12 or 12
    return f"{hour12}:{minute:02d} {period}"

def _get_tz(tz_name: str):
    if tz_name in ("Asia/Kolkata", "IST", "Asia/Calcutta"):
        return timezone(timedelta(hours=5, minutes=30))
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        return timezone.utc

def service_hours_status(now=None):
    try:
        tz_name = optional_env("SERVICE_HOURS_TZ", DEFAULT_TZ)
        start_h, start_m = _parse_hhmm(optional_env("SERVICE_HOURS_START", DEFAULT_START), DEFAULT_START)
        end_h, end_m = _parse_hhmm(optional_env("SERVICE_HOURS_END", DEFAULT_END), DEFAULT_END)

        tz = _get_tz(tz_name)
        now_local = now or datetime.now(tz)
        if now_local.tzinfo is None:
            now_local = now_local.replace(tzinfo=tz)
        else:
            now_local = now_local.astimezone(tz)
    except Exception:
        tz_name = DEFAULT_TZ
        start_h, start_m = 10, 0
        end_h, end_m = 19, 0
        tz = timezone(timedelta(hours=5, minutes=30))
        now_local = now or datetime.now(tz)

    start_minutes = start_h * 60 + start_m
    end_minutes = end_h * 60 + end_m
    current_minutes = now_local.hour * 60 + now_local.minute

    if start_minutes <= end_minutes:
        is_open = start_minutes <= current_minutes < end_minutes
    else:
        is_open = current_minutes >= start_minutes or current_minutes < end_minutes

    current_seconds = now_local.hour * 3600 + now_local.minute * 60 + now_local.second
    target_h, target_m = (end_h, end_m) if is_open else (start_h, start_m)
    target_seconds = target_h * 3600 + target_m * 60

    if target_seconds <= current_seconds:
        target_seconds += 24 * 3600

    seconds_until_next_transition = target_seconds - current_seconds

    start_label = _format_display_time(start_h, start_m)
    end_label = _format_display_time(end_h, end_m)

    closed_message = (
        f"InterviewCoach is under maintenance from {end_label} until {start_label} ({tz_name}). "
        f"We are live daily from {start_label} to {end_label} — stay tuned and check back when we open."
    )

    return {
        "is_open": is_open,
        "timezone": tz_name,
        "start": f"{start_h:02d}:{start_m:02d}",
        "end": f"{end_h:02d}:{end_m:02d}",
        "now_local": now_local.isoformat(),
        "seconds_until_next_transition": seconds_until_next_transition,
        "title": "Under maintenance" if not is_open else "",
        "message": closed_message if not is_open else "",
    }
