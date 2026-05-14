from __future__ import annotations

import json
import re
from pathlib import Path

from .items import find_media_files, resolve_item_title


def export_to_obsidian(path: Path, vault: Path) -> list[Path]:
    exported: list[Path] = []
    for item_dir in _iter_item_dirs(path):
        meta_path = item_dir / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        title = resolve_item_title(item_dir, meta)
        note_dir = vault / _date_folder(item_dir)
        note_dir.mkdir(parents=True, exist_ok=True)
        note_path = _resolve_note_path(note_dir, title, item_dir, meta)
        note_path.write_text(
            _build_note(item_dir, meta, title),
            encoding="utf-8",
        )
        exported.append(note_path)
    return exported


def _iter_item_dirs(path: Path) -> list[Path]:
    if (path / "meta.json").exists():
        return [path]
    return sorted(parent for parent in path.iterdir() if (parent / "meta.json").exists())


def _date_folder(item_dir: Path) -> str:
    parent = item_dir.parent.name
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", parent):
        return parent
    return "Unsorted"


def _resolve_note_path(note_dir: Path, title: str, item_dir: Path, meta: dict) -> Path:
    existing = _find_existing_note(note_dir, item_dir, meta)
    if existing:
        return existing
    return _unique_note_path(note_dir, title)


def _find_existing_note(note_dir: Path, item_dir: Path, meta: dict) -> Path | None:
    source_url = meta.get("final_url") or meta.get("requested_url") or ""
    local_folder = str(item_dir.resolve())
    for path in sorted(note_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if local_folder and f"local_folder: {json.dumps(local_folder, ensure_ascii=False)}" in text:
            return path
        if source_url and f"source_url: {json.dumps(source_url, ensure_ascii=False)}" in text:
            return path
    return None


def _unique_note_path(note_dir: Path, title: str) -> Path:
    base = _safe_filename(title) or "未命名素材"
    path = note_dir / f"{base}.md"
    if not path.exists():
        return path

    counter = 2
    while True:
        candidate = note_dir / f"{base}-{counter}.md"
        if not candidate.exists():
            return candidate
        counter += 1


def _safe_filename(title: str) -> str:
    title = re.sub(r"[\\/:*?\"<>|]", "-", title)
    title = re.sub(r"\s+", " ", title).strip(" .")
    return title[:120].strip()


def _build_note(item_dir: Path, meta: dict, title: str) -> str:
    media_files = find_media_files(item_dir)
    summary = _read_optional(item_dir / "summary.md")
    creator_report = _read_optional(item_dir / "analysis" / "creator_report.md")
    codex_brief = _read_optional(item_dir / "analysis" / "codex_brief.md")
    content = _read_optional(item_dir / "content.md")
    source_url = meta.get("final_url") or meta.get("requested_url") or ""
    platform = meta.get("platform") or "unknown"

    lines = [
        "---",
        f"platform: {platform}",
        f"source_url: {json.dumps(source_url, ensure_ascii=False)}",
        f"archived_at: {json.dumps(meta.get('archived_at') or '', ensure_ascii=False)}",
        f"local_folder: {json.dumps(str(item_dir.resolve()), ensure_ascii=False)}",
        "tags:",
        "  - content-vault",
        f"  - {platform}",
        "---",
        "",
        f"# {title}",
        "",
        "## 原始素材",
        "",
        f"- 平台: {platform}",
        f"- 原始链接: {source_url}",
        f"- 本地目录: `{item_dir.resolve()}`",
    ]
    if media_files:
        lines.append("- 视频文件:")
        lines.extend(f"  - `{path.resolve()}`" for path in media_files)
    else:
        lines.append("- 视频文件: 未找到")

    lines.extend(["", "## 内容摘要", ""])
    lines.append(_strip_summary_title(summary) if summary else "暂无 summary.md。")

    if creator_report:
        lines.extend(["", "## 二创报告", ""])
        lines.append(_strip_summary_title(creator_report))

    if codex_brief:
        lines.extend(["", "## Codex 分析包", ""])
        lines.append(_strip_summary_title(codex_brief))

    lines.extend(["", "## 归档正文", ""])
    lines.append(content if content else "暂无 content.md。")

    return "\n".join(lines).strip() + "\n"


def _read_optional(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _strip_summary_title(summary: str) -> str:
    lines = summary.splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).strip()
    return summary
