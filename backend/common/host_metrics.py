"""Collect Linux host metrics (CPU, RAM, disk, load) as JSON-serializable dicts."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time


def _read_meminfo():
    info = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, _, value = line.partition(":")
                info[key.strip()] = int(value.strip().split()[0]) * 1024
    except OSError:
        pass
    return info


def _cpu_percent(interval: float = 0.25):
    def snapshot():
        with open("/proc/stat", encoding="utf-8") as handle:
            parts = handle.readline().split()
        values = list(map(int, parts[1:8]))
        idle = values[3] + values[4]
        return sum(values), idle

    total_a, idle_a = snapshot()
    time.sleep(interval)
    total_b, idle_b = snapshot()
    delta_total = total_b - total_a
    delta_idle = idle_b - idle_a
    if delta_total <= 0:
        return None
    return round(max(0.0, min(100.0, 100.0 * (1.0 - delta_idle / delta_total))), 1)


def collect_linux_metrics(role: str, host_label: str = ""):
    mem = _read_meminfo()
    mem_total = mem.get("MemTotal", 0)
    mem_available = mem.get("MemAvailable", mem.get("MemFree", 0))
    mem_used = max(0, mem_total - mem_available) if mem_total else 0
    mem_percent = round(100.0 * mem_used / mem_total, 1) if mem_total else None

    disk = shutil.disk_usage("/")
    disk_percent = round(100.0 * disk.used / disk.total, 1) if disk.total else None

    load_parts = []
    try:
        with open("/proc/loadavg", encoding="utf-8") as handle:
            load_parts = handle.read().strip().split()
    except OSError:
        pass

    cpu_count = os.cpu_count() or 1
    load_1 = float(load_parts[0]) if load_parts else 0.0
    load_percent = round(min(100.0, 100.0 * load_1 / cpu_count), 1)

    uptime_seconds = None
    try:
        with open("/proc/uptime", encoding="utf-8") as handle:
            uptime_seconds = int(float(handle.read().split()[0]))
    except (OSError, ValueError, IndexError):
        pass

    return {
        "role": role,
        "host": host_label or role,
        "available": True,
        "cpu_percent": _cpu_percent(),
        "load_1": load_1,
        "load_5": float(load_parts[1]) if len(load_parts) > 1 else None,
        "load_15": float(load_parts[2]) if len(load_parts) > 2 else None,
        "load_percent": load_percent,
        "cpu_cores": cpu_count,
        "memory_total_bytes": mem_total,
        "memory_used_bytes": mem_used,
        "memory_available_bytes": mem_available,
        "memory_percent": mem_percent,
        "disk_total_bytes": disk.total,
        "disk_used_bytes": disk.used,
        "disk_free_bytes": disk.free,
        "disk_percent": disk_percent,
        "uptime_seconds": uptime_seconds,
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def collect_via_ssh(role: str, host: str, ssh_key: str, ssh_user: str = "ubuntu", timeout: int = 12):
    script_path = os.path.join(os.path.dirname(__file__), "host_metrics_remote.py")
    if not os.path.isfile(script_path):
        return {
            "role": role,
            "host": host,
            "available": False,
            "error": "Remote metrics script missing on API host",
        }

    command = [
        "ssh",
        "-i",
        ssh_key,
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={timeout}",
        "-o",
        "StrictHostKeyChecking=accept-new",
        f"{ssh_user}@{host}",
        f"python3 - {role} {host}",
    ]
    try:
        with open(script_path, encoding="utf-8") as script_handle:
            completed = subprocess.run(
                command,
                input=script_handle.read(),
                capture_output=True,
                text=True,
                timeout=timeout + 5,
                check=False,
            )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "ssh failed").strip()[:300]
            return {
                "role": role,
                "host": host,
                "available": False,
                "error": detail,
            }
        payload = json.loads((completed.stdout or "").strip() or "{}")
        payload.setdefault("role", role)
        payload.setdefault("host", host)
        return payload
    except subprocess.TimeoutExpired:
        return {"role": role, "host": host, "available": False, "error": "SSH timed out"}
    except json.JSONDecodeError as exc:
        return {"role": role, "host": host, "available": False, "error": f"Invalid metrics JSON: {exc}"}
    except OSError as exc:
        return {"role": role, "host": host, "available": False, "error": str(exc)}
