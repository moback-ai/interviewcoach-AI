import os
import shutil
from urllib.parse import urlparse

from flask import Response, send_from_directory
from werkzeug.security import safe_join
from werkzeug.utils import secure_filename

from common.runtime_config import load_runtime_config, optional_env, require_env
from common.storage_s3 import (
    delete_s3_objects,
    list_s3_folder,
    read_bytes_s3,
    save_bytes_s3,
    s3_object_exists,
    use_s3_storage,
)

load_runtime_config()

PROTECTED_STORAGE_PREFIXES = ("resumes", "audio", "avatars")
FILES_API_PREFIX = "/api/files/"


def _storage_path():
    return require_env("STORAGE_PATH")


def _public_storage_url():
    return optional_env("PUBLIC_STORAGE_URL", "").rstrip("/")


def _storage_root() -> str:
    return os.path.realpath(_storage_path())


def _path_segments_valid(normalized: str) -> bool:
    parts = normalized.split("/")
    return not any(part in ("", ".", "..") for part in parts)


def normalize_relative_path(relative_path: str) -> str | None:
    """Normalize a relative path and reject traversal segments."""
    clean = (relative_path or "").strip().replace("\\", "/")
    if not clean or os.path.isabs(clean):
        return None

    raw_parts = clean.split("/")
    if any(part in ("", ".", "..") for part in raw_parts):
        return None

    normalized = os.path.normpath(clean).replace("\\", "/")
    if normalized in ("", ".", "..") or normalized.startswith("../"):
        return None
    if not _path_segments_valid(normalized):
        return None
    return normalized


def validated_protected_relative_path(relative_path: str) -> str | None:
    """Normalize and require resumes/audio/avatars scoped storage paths."""
    clean = normalize_relative_path(relative_path)
    if not clean:
        return None
    parts = clean.split("/")
    if len(parts) < 2 or parts[0] not in PROTECTED_STORAGE_PREFIXES:
        return None
    return clean


def _sanitize_path_segment(segment: str) -> str | None:
    value = str(segment).strip()
    if not value or value in (".", ".."):
        return None
    if "/" in value or "\\" in value:
        return None
    safe = secure_filename(value)
    if not safe or safe != value:
        return None
    return safe


def build_protected_storage_path(prefix: str, *segments: str) -> str | None:
    """Build a validated storage path from trusted prefix and sanitized segments."""
    if prefix not in PROTECTED_STORAGE_PREFIXES:
        return None
    parts = [prefix]
    for segment in segments:
        clean_segment = _sanitize_path_segment(segment)
        if not clean_segment:
            return None
        parts.append(clean_segment)
    return validated_protected_relative_path("/".join(parts))


def _path_within_root(root: str, target: str) -> bool:
    try:
        return os.path.commonpath([root, target]) == root
    except ValueError:
        return False


def _resolve_under_storage_root(relative_path: str) -> str | None:
    """Resolve a validated relative path under STORAGE_PATH using safe_join."""
    clean = validated_protected_relative_path(relative_path)
    if not clean:
        return None
    joined = safe_join(_storage_path(), *clean.split("/"))
    if not joined:
        return None
    storage_root = _storage_root()
    resolved = os.path.realpath(joined)
    if not _path_within_root(storage_root, resolved):
        return None
    return resolved


def _ensure(folder: str) -> str:
    path = os.path.join(_storage_path(), folder)
    os.makedirs(path, exist_ok=True)
    return path


def protected_file_url(relative_path: str) -> str:
    """JWT-protected download path (frontend resolves full URL via API base)."""
    clean = (relative_path or "").strip().lstrip("/").replace("\\", "/")
    return f"{FILES_API_PREFIX}{clean}"


def normalize_file_url(url_or_path: str | None) -> str | None:
    """Rewrite legacy /storage/ URLs to protected /api/files/ URLs."""
    if not url_or_path:
        return url_or_path
    value = str(url_or_path).strip()
    if not value:
        return value
    if value.startswith(FILES_API_PREFIX):
        return value
    relative = resolve_relative_path(value)
    if relative:
        return protected_file_url(relative)
    return value


def resolve_relative_path(url_or_path: str | None) -> str | None:
    """Normalize storage URLs or raw paths to a validated relative storage path."""
    if not url_or_path:
        return None
    value = str(url_or_path).strip().replace("\\", "/")
    if not value:
        return None

    candidate = None
    if value.startswith(FILES_API_PREFIX):
        candidate = value[len(FILES_API_PREFIX):].lstrip("/")
    else:
        public_base = _public_storage_url()
        if public_base and value.startswith(public_base):
            candidate = value[len(public_base):].lstrip("/")
        else:
            parsed = urlparse(value)
            if parsed.scheme and parsed.path:
                path = parsed.path.lstrip("/")
                if path.startswith("storage/"):
                    candidate = path[len("storage/"):]
                elif path.startswith("api/files/"):
                    candidate = path[len("api/files/"):]
            elif value.startswith("/storage/"):
                candidate = value[len("/storage/"):]
            elif value.startswith("storage/"):
                candidate = value[len("storage/"):]
            elif "/" in value and not value.startswith("/") and "://" not in value:
                candidate = value.lstrip("/")

    if not candidate:
        return None
    return validated_protected_relative_path(candidate)


def user_owns_storage_path(user_id: str, relative_path: str) -> bool:
    clean = validated_protected_relative_path(relative_path)
    if not clean:
        return False
    parts = clean.split("/")
    folder, owner_id = parts[0], parts[1]
    return str(owner_id) == str(user_id)


def storage_file_exists(relative_path: str) -> bool:
    clean = validated_protected_relative_path(relative_path)
    if not clean:
        return False
    if use_s3_storage():
        return s3_object_exists(clean)
    return safe_storage_file_path(clean) is not None


def send_storage_file(clean_path: str):
    """Serve a validated protected file from local disk or S3."""
    import mimetypes

    mimetype = mimetypes.guess_type(clean_path)[0] or "application/octet-stream"
    if use_s3_storage():
        data = read_bytes(clean_path)
        return Response(data, mimetype=mimetype)
    storage_root = os.path.realpath(require_env("STORAGE_PATH"))
    return send_from_directory(storage_root, clean_path, mimetype=mimetype, as_attachment=False)


def safe_storage_file_path(relative_path: str) -> str | None:
    """Resolve relative path under STORAGE_PATH; return None if outside root or missing."""
    clean = validated_protected_relative_path(relative_path)
    if not clean:
        return None
    if use_s3_storage():
        return clean if s3_object_exists(clean) else None
    file_path = _resolve_under_storage_root(relative_path)
    if not file_path or not os.path.isfile(file_path):
        return None
    return file_path


def safe_storage_dir_path(folder: str) -> str | None:
    """Resolve folder under STORAGE_PATH; return None if outside root."""
    dir_path = _resolve_under_storage_root(folder)
    if not dir_path or not os.path.isdir(dir_path):
        return None
    return dir_path


def _file_result(relative: str, stored_path: str, file_size: int) -> dict:
    protected = protected_file_url(relative)
    return {
        "stored_path": stored_path,
        "relative_path": relative,
        "protected_url": protected,
        "public_url": protected,
        "file_size": file_size,
    }


def save_bytes(data: bytes, folder: str, filename: str) -> dict:
    """Save raw bytes to storage. Returns path info."""
    if use_s3_storage():
        return save_bytes_s3(data, folder, filename)
    dir_path = _ensure(folder)
    file_path = os.path.join(dir_path, filename)
    with open(file_path, 'wb') as f:
        f.write(data)
    relative = f"{folder}/{filename}"
    return _file_result(relative, file_path, len(data))


def save_from_path(src: str, folder: str, filename: str) -> dict:
    """Copy an existing file into storage."""
    if use_s3_storage():
        with open(src, "rb") as handle:
            return save_bytes_s3(handle.read(), folder, filename)
    dir_path = _ensure(folder)
    dest = os.path.join(dir_path, filename)
    shutil.copy2(src, dest)
    relative = f"{folder}/{filename}"
    return _file_result(relative, dest, os.path.getsize(dest))


def read_bytes(relative_path: str) -> bytes:
    """Read file from storage."""
    clean = validated_protected_relative_path(relative_path)
    if not clean:
        raise FileNotFoundError(f"Storage file not found: {relative_path}")
    if use_s3_storage():
        return read_bytes_s3(clean)
    file_path = safe_storage_file_path(clean)
    if not file_path:
        raise FileNotFoundError(f"Storage file not found: {relative_path}")
    with open(file_path, 'rb') as f:
        return f.read()


def list_folder(folder: str) -> list:
    """List files in a storage folder."""
    if use_s3_storage():
        return list_s3_folder(folder)
    dir_path = safe_storage_dir_path(folder)
    if not dir_path:
        return []

    storage_root = _storage_root()
    files = []
    for fname in os.listdir(dir_path):
        safe_name = os.path.basename(fname)
        if safe_name != fname or safe_name in ("", ".", ".."):
            continue
        joined = safe_join(dir_path, safe_name)
        if not joined:
            continue
        canonical_fpath = os.path.realpath(joined)
        if not _path_within_root(storage_root, canonical_fpath):
            continue
        if not os.path.isfile(canonical_fpath):
            continue
        relative = os.path.relpath(canonical_fpath, storage_root).replace("\\", "/")
        if not validated_protected_relative_path(relative):
            continue
        entry = _file_result(relative, canonical_fpath, os.path.getsize(canonical_fpath))
        entry["name"] = safe_name
        files.append(entry)
    return files


def delete_files(relative_paths: list):
    """Delete a list of files by relative path."""
    if use_s3_storage():
        clean_paths = []
        for rel in relative_paths:
            clean = validated_protected_relative_path(rel)
            if clean:
                clean_paths.append(clean)
        delete_s3_objects(clean_paths)
        return
    for rel in relative_paths:
        clean = validated_protected_relative_path(rel)
        if not clean:
            continue
        file_path = safe_storage_file_path(clean)
        if file_path:
            os.remove(file_path)


def public_url(relative_path: str) -> str:
    """Return protected URL for stored files (legacy name kept for callers)."""
    return protected_file_url(relative_path)
