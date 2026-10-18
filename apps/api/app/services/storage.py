"""Local file storage for images. Paths are stored relative to data_dir and never taken from user input."""
from pathlib import Path

from app.config import Settings


def _root(settings: Settings) -> Path:
    return Path(settings.data_dir).resolve()


def save_bytes(settings: Settings, user_id: str, doc_id: str, ext: str, data: bytes) -> str:
    folder = _root(settings) / "uploads" / user_id
    folder.mkdir(parents=True, exist_ok=True)
    rel = f"uploads/{user_id}/{doc_id}{ext}"
    (_root(settings) / rel).write_bytes(data)
    return rel


def abs_path(settings: Settings, rel: str) -> Path:
    path = (_root(settings) / rel).resolve()
    if _root(settings) not in path.parents:  # defence in depth against path traversal
        raise ValueError("Invalid storage path")
    return path


def remove(settings: Settings, rel: str | None) -> None:
    if not rel:
        return
    try:
        abs_path(settings, rel).unlink(missing_ok=True)
    except (ValueError, OSError):
        pass
