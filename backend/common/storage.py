import os
import shutil
from urllib.parse import urlparse

from common.runtime_config import load_runtime_config, optional_env, require_env

load_runtime_config()

PROTECTED_STORAGE_PREFIXES = ("resumes", "audio", "avatars")
FILES_API_PREFIX = "/api/files/"


def _storage_path():
    return require_env("STORAGE_PATH")


def _public_storage_url():
    return optional_env("PUBLIC_STORAGE_URL", "").rstrip("/")


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
    """Normalize storage URLs or raw paths to a relative storage path."""
    if not url_or_path:
        return None
    value = str(url_or_path).strip().replace("\\", "/")
    if not value:
        return None

    if value.startswith(FILES_API_PREFIX):
        return value[len(FILES_API_PREFIX):].lstrip("/")

    public_base = _public_storage_url()
    if public_base and value.startswith(public_base):
        return value[len(public_base):].lstrip("/")

    parsed = urlparse(value)
    if parsed.scheme and parsed.path:
        path = parsed.path.lstrip("/")
        if path.startswith("storage/"):
            return path[len("storage/"):]
        if path.startswith("api/files/"):
            return path[len("api/files/"):]

    if value.startswith("/storage/"):
        return value[len("/storage/"):]

    if value.startswith("storage/"):
        return value[len("storage/"):]

    if "/" in value and not value.startswith("/") and "://" not in value:
        return value.lstrip("/")

    return None


def user_owns_storage_path(user_id: str, relative_path: str) -> bool:
    clean = (relative_path or "").strip().replace("\\", "/").lstrip("/")
    parts = clean.split("/")
    if len(parts) < 2:
        return False
    folder, owner_id = parts[0], parts[1]
    if folder not in PROTECTED_STORAGE_PREFIXES:
        return False
    return str(owner_id) == str(user_id)


def normalize_relative_path(relative_path: str) -> str | None:
    clean = (relative_path or "").strip().replace("\\", "/")
    if not clean or os.path.isabs(clean):
        return None
    normalized = os.path.normpath(clean).replace("\\", "/")
    if normalized in ("", ".", "..") or normalized.startswith("../"):
        return None
    return normalized


def _path_within_root(root: str, target: str) -> bool:
    try:
        return os.path.commonpath([root, target]) == root
    except ValueError:
        return False


def safe_storage_file_path(relative_path: str) -> str | None:
    """Resolve relative path under STORAGE_PATH; return None if outside root."""
    clean = normalize_relative_path(relative_path)
    if not clean:
        return None

    storage_root = os.path.realpath(_storage_path())
    file_path = os.path.realpath(os.path.join(storage_root, clean))
    if not _path_within_root(storage_root, file_path):
        return None
    if not os.path.isfile(file_path):
        return None
    return file_path


def safe_storage_dir_path(folder: str) -> str | None:
    """Resolve folder under STORAGE_PATH; return None if outside root."""
    clean = normalize_relative_path(folder)
    if not clean:
        return None

    storage_root = os.path.realpath(_storage_path())
    dir_path = os.path.realpath(os.path.join(storage_root, clean))
    if not _path_within_root(storage_root, dir_path):
        return None
    if not os.path.isdir(dir_path):
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
    dir_path = _ensure(folder)
    file_path = os.path.join(dir_path, filename)
    with open(file_path, 'wb') as f:
        f.write(data)
    relative = f"{folder}/{filename}"
    return _file_result(relative, file_path, len(data))


def save_from_path(src: str, folder: str, filename: str) -> dict:
    """Copy an existing file into storage."""
    dir_path = _ensure(folder)
    dest = os.path.join(dir_path, filename)
    shutil.copy2(src, dest)
    relative = f"{folder}/{filename}"
    return _file_result(relative, dest, os.path.getsize(dest))


def read_bytes(relative_path: str) -> bytes:
    """Read file from storage."""
    file_path = safe_storage_file_path(relative_path)
    if not file_path:
        raise FileNotFoundError(f"Storage file not found: {relative_path}")
    with open(file_path, 'rb') as f:
        return f.read()


def list_folder(folder: str) -> list:
    """List files in a storage folder."""
    dir_path = safe_storage_dir_path(folder)
    if not dir_path:
        return []
    files = []
    for fname in os.listdir(dir_path):
        fpath = os.path.join(dir_path, fname)
        if os.path.isfile(fpath):
            relative = f"{folder}/{fname}"
            entry = _file_result(relative, fpath, os.path.getsize(fpath))
            entry["name"] = fname
            files.append(entry)
    return files


def delete_files(relative_paths: list):
    """Delete a list of files by relative path."""
    for rel in relative_paths:
        file_path = safe_storage_file_path(rel)
        if file_path:
            os.remove(file_path)


def public_url(relative_path: str) -> str:
    """Return protected URL for stored files (legacy name kept for callers)."""
    return protected_file_url(relative_path)
