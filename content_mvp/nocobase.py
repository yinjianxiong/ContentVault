from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .items import find_media_files, resolve_item_title


def build_processed_asset_payload(item_dir: Path) -> dict:
    meta_path = item_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    media_files = find_media_files(item_dir)
    primary_media = media_files[0] if media_files else None
    frame_paths = sorted((item_dir / "analysis" / "frames").glob("*.jpg"))

    return {
        "source_url": meta.get("requested_url") or "",
        "final_url": meta.get("final_url") or meta.get("requested_url") or "",
        "platform": meta.get("platform") or "unknown",
        "title": resolve_item_title(item_dir, meta),
        "archive_date": _archive_date(item_dir),
        "local_folder": str(item_dir.resolve()),
        "media_paths": [str(path.resolve()) for path in media_files],
        "primary_media_path": str(primary_media.resolve()) if primary_media else "",
        "cover_paths": [str(path.resolve()) for path in frame_paths],
        "duration_seconds": None,
        "file_size_bytes": primary_media.stat().st_size if primary_media else None,
        "download_status": _download_status(meta, media_files),
        "analysis_status": _analysis_status(item_dir),
        "summary_md": _read_optional(item_dir / "summary.md"),
        "codex_brief_md": _read_optional(item_dir / "analysis" / "codex_brief.md"),
        "creator_report_md": _read_optional(item_dir / "analysis" / "creator_report.md"),
        "obsidian_note_path": meta.get("obsidian_note_path") or "",
        "raw_meta": meta,
    }


def _archive_date(item_dir: Path) -> str:
    parent = item_dir.parent.name
    try:
        return date.fromisoformat(parent).isoformat()
    except ValueError:
        return ""


def _download_status(meta: dict, media_files: list[Path]) -> str:
    if media_files:
        status = (meta.get("media_download") or {}).get("status")
        if status == "imported":
            return "imported"
        return "downloaded"
    if (meta.get("media_download") or {}).get("status") == "failed":
        return "failed"
    return "none"


def _analysis_status(item_dir: Path) -> str:
    if (item_dir / "analysis" / "creator_report.md").exists():
        return "report_ready"
    if (item_dir / "analysis" / "codex_brief.md").exists():
        return "brief_ready"
    if (item_dir / "summary.md").exists():
        return "summary_ready"
    return "none"


def _read_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()
