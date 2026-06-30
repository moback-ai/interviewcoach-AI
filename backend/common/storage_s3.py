from __future__ import annotations

import os
from typing import Iterator

from common.runtime_config import optional_env


def storage_backend() -> str:
    return optional_env("STORAGE_BACKEND", "local").strip().lower() or "local"


def use_s3_storage() -> bool:
    return storage_backend() == "s3"


def _boto3():
    import boto3

    return boto3


def _bucket() -> str:
    bucket = optional_env("S3_BUCKET", "").strip()
    if not bucket:
        raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
    return bucket


def _region() -> str:
    return optional_env("AWS_REGION", "ap-south-1")


def _s3_key(relative_path: str) -> str:
    return relative_path.strip().lstrip("/").replace("\\", "/")


def s3_object_exists(relative_path: str) -> bool:
    client = _boto3().client("s3", region_name=_region())
    key = _s3_key(relative_path)
    try:
        client.head_object(Bucket=_bucket(), Key=key)
        return True
    except Exception:
        return False


def save_bytes_s3(data: bytes, folder: str, filename: str) -> dict:
    relative = f"{folder.strip('/')}/{filename}"
    key = _s3_key(relative)
    client = _boto3().client("s3", region_name=_region())
    client.put_object(Bucket=_bucket(), Key=key, Body=data)

    public_base = optional_env("PUBLIC_STORAGE_URL", "").rstrip("/")
    protected = f"/api/files/{relative}"
    public_url = f"{public_base}/{key}" if public_base else protected
    return {
        "stored_path": f"s3://{_bucket()}/{key}",
        "relative_path": relative,
        "protected_url": protected,
        "public_url": public_url,
        "file_size": len(data),
    }


def read_bytes_s3(relative_path: str) -> bytes:
    client = _boto3().client("s3", region_name=_region())
    response = client.get_object(Bucket=_bucket(), Key=_s3_key(relative_path))
    return response["Body"].read()


def delete_s3_objects(relative_paths: list[str]) -> None:
    if not relative_paths:
        return
    client = _boto3().client("s3", region_name=_region())
    bucket = _bucket()
    for rel in relative_paths:
        key = _s3_key(rel)
        try:
            client.delete_object(Bucket=bucket, Key=key)
        except Exception:
            pass


def list_s3_folder(folder: str) -> list[dict]:
    client = _boto3().client("s3", region_name=_region())
    bucket = _bucket()
    prefix = _s3_key(folder).rstrip("/") + "/"
    paginator = client.get_paginator("list_objects_v2")
    files: list[dict] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents") or []:
            key = obj.get("Key") or ""
            if not key or key.endswith("/"):
                continue
            relative = key
            name = os.path.basename(key)
            protected = f"/api/files/{relative}"
            files.append(
                {
                    "name": name,
                    "relative_path": relative,
                    "stored_path": f"s3://{bucket}/{key}",
                    "protected_url": protected,
                    "public_url": protected,
                    "file_size": int(obj.get("Size") or 0),
                }
            )
    return files


def copy_local_to_s3(local_root: str, prefix: str = "") -> Iterator[str]:
    """Yield S3 keys uploaded from local_root (migration helper)."""
    client = _boto3().client("s3", region_name=_region())
    bucket = _bucket()
    local_root = os.path.realpath(local_root)
    for dirpath, _, filenames in os.walk(local_root):
        for fname in filenames:
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, local_root).replace("\\", "/")
            key = _s3_key(f"{prefix}/{rel}" if prefix else rel)
            client.upload_file(full, bucket, key)
            yield key
