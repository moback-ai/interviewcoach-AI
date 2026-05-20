#!/usr/bin/env python3
"""Run on remote hosts via: python3 - <role> <host_label>  (script on stdin)."""
import json
import os
import shutil
import sys
import time


def cpu_percent(interval=0.25):
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


def main():
    role = sys.argv[1] if len(sys.argv) > 1 else "remote"
    host_label = sys.argv[2] if len(sys.argv) > 2 else role

    mem = {}
    with open("/proc/meminfo", encoding="utf-8") as handle:
        for line in handle:
            key, _, value = line.partition(":")
            mem[key.strip()] = int(value.strip().split()[0]) * 1024

    mem_total = mem.get("MemTotal", 0)
    mem_available = mem.get("MemAvailable", mem.get("MemFree", 0))
    mem_used = max(0, mem_total - mem_available) if mem_total else 0
    mem_percent = round(100.0 * mem_used / mem_total, 1) if mem_total else None

    disk = shutil.disk_usage("/")
    disk_percent = round(100.0 * disk.used / disk.total, 1) if disk.total else None

    with open("/proc/loadavg", encoding="utf-8") as handle:
        load_parts = handle.read().strip().split()

    cpu_count = os.cpu_count() or 1
    load_1 = float(load_parts[0]) if load_parts else 0.0

    with open("/proc/uptime", encoding="utf-8") as handle:
        uptime_seconds = int(float(handle.read().split()[0]))

    print(json.dumps({
        "role": role,
        "host": host_label,
        "available": True,
        "cpu_percent": cpu_percent(),
        "load_1": load_1,
        "load_5": float(load_parts[1]) if len(load_parts) > 1 else None,
        "load_15": float(load_parts[2]) if len(load_parts) > 2 else None,
        "load_percent": round(min(100.0, 100.0 * load_1 / cpu_count), 1),
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
    }))


if __name__ == "__main__":
    main()
