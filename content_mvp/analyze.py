from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .extract import extract_page
from .items import find_media_files, resolve_item_title
from .summarize import build_summary
from .transcribe import transcribe_item


@dataclass
class AnalyzeResult:
    item_dir: Path
    title: str
    summary_path: Path
    brief_path: Path
    frame_paths: list[Path]


def analyze_archive(path: Path, *, frame_count: int = 6) -> list[AnalyzeResult]:
    results: list[AnalyzeResult] = []
    for item_dir in _iter_item_dirs(path):
        results.append(analyze_item(item_dir, frame_count=frame_count))
    return results


def analyze_item(item_dir: Path, *, frame_count: int = 6) -> AnalyzeResult:
    meta_path = item_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    extracted = _load_extracted(item_dir)
    title = resolve_item_title(item_dir, meta)
    summary_path = item_dir / "summary.md"
    summary_path.write_text(
        build_summary(meta, extracted, title=title),
        encoding="utf-8",
    )

    media_files = find_media_files(item_dir)
    transcribe_item(item_dir)
    frame_paths = _extract_frames(media_files[0], item_dir, frame_count) if media_files else []
    brief_path = item_dir / "analysis" / "codex_brief.md"
    brief_path.parent.mkdir(parents=True, exist_ok=True)
    brief_path.write_text(
        _build_codex_brief(item_dir, meta, extracted, title, media_files, frame_paths),
        encoding="utf-8",
    )
    return AnalyzeResult(
        item_dir=item_dir,
        title=title,
        summary_path=summary_path,
        brief_path=brief_path,
        frame_paths=frame_paths,
    )


def _iter_item_dirs(path: Path) -> list[Path]:
    if (path / "meta.json").exists():
        return [path]
    return sorted(parent for parent in path.iterdir() if (parent / "meta.json").exists())


def _load_extracted(item_dir: Path) -> dict:
    raw_path = item_dir / "raw.html"
    if raw_path.exists():
        return extract_page(raw_path.read_text(encoding="utf-8", errors="replace"))
    return {
        "title": "",
        "description": "",
        "image": "",
        "video": "",
        "text": "",
        "meta": {},
        "image_candidates": [],
    }


def _extract_frames(media_path: Path, item_dir: Path, frame_count: int) -> list[Path]:
    if frame_count <= 0 or not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        return []

    duration = _probe_duration(media_path)
    if duration <= 0:
        return []

    frames_dir = item_dir / "analysis" / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    timestamps = _sample_timestamps(duration, frame_count)
    frame_paths: list[Path] = []
    for index, timestamp in enumerate(timestamps, start=1):
        output_path = frames_dir / f"frame_{index:02d}.jpg"
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.2f}",
            "-i",
            str(media_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if completed.returncode == 0 and output_path.exists():
            frame_paths.append(output_path)
    return frame_paths


def _probe_duration(media_path: Path) -> float:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ],
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if completed.returncode != 0:
        return 0.0
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return 0.0


def _sample_timestamps(duration: float, frame_count: int) -> list[float]:
    if frame_count == 1:
        return [max(duration * 0.5, 0.0)]
    start = min(1.0, duration * 0.08)
    end = max(duration - min(1.0, duration * 0.08), start)
    step = (end - start) / (frame_count - 1)
    return [start + step * index for index in range(frame_count)]


def _build_codex_brief(
    item_dir: Path,
    meta: dict,
    extracted: dict,
    title: str,
    media_files: list[Path],
    frame_paths: list[Path],
) -> str:
    source_url = meta.get("final_url") or meta.get("requested_url") or ""
    text = (extracted.get("text") or "").strip()
    description = (meta.get("description") or extracted.get("description") or "").strip()

    lines = [
        f"# Codex 二创分析包: {title}",
        "",
        "## 素材信息",
        "",
        f"- 标题: {title}",
        f"- 平台: {meta.get('platform') or 'unknown'}",
        f"- 原始链接: {source_url}",
        f"- 本地目录: `{item_dir.resolve()}`",
    ]
    if media_files:
        lines.append("- 本地视频:")
        lines.extend(f"  - `{path.resolve()}`" for path in media_files)
    else:
        lines.append("- 本地视频: 未找到")

    transcript_path = item_dir / "analysis" / "transcript.original.md"
    translated_subtitles = sorted((item_dir / "analysis").glob("subtitles.*.srt"))
    if transcript_path.exists():
        lines.append(f"- 转写文本: `{transcript_path.resolve()}`")
    if translated_subtitles:
        lines.append("- 字幕文件:")
        lines.extend(f"  - `{path.resolve()}`" for path in translated_subtitles)

    if description:
        lines.extend(["", "## 页面描述", "", description])

    lines.extend(["", "## 视频抽帧", ""])
    if frame_paths:
        for frame_path in frame_paths:
            lines.append(f"![{frame_path.stem}]({frame_path.resolve()})")
    else:
        lines.append("未生成抽帧。需要本机安装 ffmpeg/ffprobe，或素材本身不是视频。")

    lines.extend(
        [
            "",
            "## 可供分析的正文",
            "",
            text if text else "网页正文为空，优先结合标题、视频文件名和抽帧画面分析。",
            "",
            "## 给 Codex 的分析任务",
            "",
            "请基于以上素材做二创拆解，输出:",
            "",
            "1. 这条内容实际讲了什么，按时间线或段落拆成 5-8 个信息点。",
            "2. 原内容的叙事钩子、情绪爽点、反转点和视觉记忆点。",
            "3. 适合二创的 3 个角度，每个角度给出目标受众、核心观点、开场 3 秒钩子。",
            "4. 一版 60-90 秒口播脚本，要求不是复述原片，而是观点化再表达。",
            "5. 可用标题 10 个，按猎奇/观点/实用/情绪共鸣分类。",
            "6. 版权与事实风险，列出需要避开的照搬点和需要核验的点。",
        ]
    )
    return "\n".join(lines).strip() + "\n"
