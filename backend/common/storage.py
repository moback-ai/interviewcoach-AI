import os
import shutil
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

STORAGE_PATH = os.getenv("STORAGE_PATH", "/apps/storage")
PUBLIC_STORAGE_URL = os.getenv("PUBLIC_STORAGE_URL", "http://localhost/storage")

def _ensure(folder: str) -> str:
    path = os.path.join(STORAGE_PATH, folder)
    os.makedirs(path, exist_ok=True)
    return path

def save_bytes(data: bytes, folder: str, filename: str) -> dict:
    """Save raw bytes to storage. Returns path info."""
    dir_path = _ensure(folder)
    file_path = os.path.join(dir_path, filename)
    with open(file_path, 'wb') as f:
        f.write(data)
    relative = f"{folder}/{filename}"
    return {
        "stored_path": file_path,
        "relative_path": relative,
        "public_url": f"{PUBLIC_STORAGE_URL}/{relative}",
        "file_size": len(data)
    }

def save_from_path(src: str, folder: str, filename: str) -> dict:
    """Copy an existing file into storage."""
    dir_path = _ensure(folder)
    dest = os.path.join(dir_path, filename)
    shutil.copy2(src, dest)
    relative = f"{folder}/{filename}"
    return {
        "stored_path": dest,
        "relative_path": relative,
        "public_url": f"{PUBLIC_STORAGE_URL}/{relative}",
        "file_size": os.path.getsize(dest)
    }

def read_bytes(relative_path: str) -> bytes:
    """Read file from storage."""
    with open(os.path.join(STORAGE_PATH, relative_path), 'rb') as f:
        return f.read()

def list_folder(folder: str) -> list:
    """List files in a storage folder."""
    dir_path = os.path.join(STORAGE_PATH, folder)
    if not os.path.exists(dir_path):
        return []
    files = []
    for fname in os.listdir(dir_path):
        fpath = os.path.join(dir_path, fname)
        if os.path.isfile(fpath):
            relative = f"{folder}/{fname}"
            files.append({
                "name": fname,
                "stored_path": fpath,
                "relative_path": relative,
                "public_url": f"{PUBLIC_STORAGE_URL}/{relative}",
                "file_size": os.path.getsize(fpath)
            })
    return files

def delete_files(relative_paths: list):
    """Delete a list of files by relative path."""
    for rel in relative_paths:
        full = os.path.join(STORAGE_PATH, rel)
        if os.path.exists(full):
            os.remove(full)

def public_url(relative_path: str) -> str:
    return f"{PUBLIC_STORAGE_URL}/{relative_path}"
