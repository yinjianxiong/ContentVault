from __future__ import annotations

import re
from pathlib import Path


MEDIA_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}


def find_media_files(item_dir: Path) -> list[Path]:
    media_dir = item_dir / "media"
    if not media_dir.exists():
        return []
    return sorted(
        (
            path
            for path in media_dir.iterdir()
            if path.is_file() and path.suffix.lower() in MEDIA_SUFFIXES
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def title_from_media_file(item_dir: Path) -> str:
    media_files = find_media_files(item_dir)
    if not media_files:
        return ""
    return _clean_media_title(media_files[0].stem)


def resolve_item_title(item_dir: Path, meta: dict) -> str:
    title = (meta.get("title") or "").strip()
    if title:
        return title
    media_title = title_from_media_file(item_dir)
    if media_title:
        return media_title
    return item_dir.name


def _clean_media_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip()
    return title
