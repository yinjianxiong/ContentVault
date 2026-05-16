from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .items import find_media_files


@dataclass
class TranscriptResult:
    status: str
    source_language: str = ""
    transcript_path: Path | None = None
    original_srt_path: Path | None = None
    reason: str = ""


def transcribe_item(
    item_dir: Path,
    *,
    model_size: str = "turbo",
    device: str = "auto",
    compute_type: str = "auto",
) -> TranscriptResult:
    media_files = find_media_files(item_dir)
    if not media_files:
        return TranscriptResult(status="skipped", reason="no media file found")
    cached = _load_cached_result(item_dir)
    if cached:
        return cached
    if not shutil.which("ffmpeg"):
        return TranscriptResult(status="skipped", reason="ffmpeg is not installed")

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return TranscriptResult(status="skipped", reason="faster-whisper is not installed")

    analysis_dir = item_dir / "analysis"
    audio_dir = analysis_dir / "audio"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    audio_dir.mkdir(parents=True, exist_ok=True)

    audio_path = audio_dir / "source.mp3"
    _extract_audio(media_files[0], audio_path)

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    raw_segments, info = model.transcribe(
        str(audio_path),
        beam_size=5,
        vad_filter=True,
    )
    segments = _normalize_segments(raw_segments)
    if not segments:
        return TranscriptResult(status="failed", reason="transcription returned no text")

    source_language = _normalize_language(getattr(info, "language", "") or "")
    transcript_path = analysis_dir / "transcript.original.md"
    original_srt_path = analysis_dir / "subtitles.original.srt"
    transcript_path.write_text(
        _build_transcript_markdown(source_language, segments),
        encoding="utf-8",
    )
    original_srt_path.write_text(_build_srt(segments), encoding="utf-8")

    result = TranscriptResult(
        status="ready",
        source_language=source_language,
        transcript_path=transcript_path,
        original_srt_path=original_srt_path,
    )
    _write_transcript_meta(item_dir, result, model_size=model_size)
    return result


def _extract_audio(media_path: Path, output_path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(media_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "64k",
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        timeout=180,
    )
    if completed.returncode != 0 or not output_path.exists():
        message = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"audio extraction failed: {message[-1000:]}")


def _normalize_segments(raw_segments: Any) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for raw in raw_segments:
        text = (getattr(raw, "text", "") or "").strip()
        if not text:
            continue
        segments.append(
            {
                "start": float(getattr(raw, "start", 0.0) or 0.0),
                "end": float(getattr(raw, "end", 0.0) or 0.0),
                "text": text,
            }
        )
    return segments


def _normalize_language(language: str) -> str:
    language = language.lower().strip()
    aliases = {
        "chinese": "zh",
        "mandarin": "zh",
        "zh-cn": "zh",
        "english": "en",
        "eng": "en",
    }
    return aliases.get(language, language)


def _build_transcript_markdown(language: str, segments: list[dict[str, Any]]) -> str:
    lines = [
        "# Transcript",
        "",
        f"- Language: {language or 'unknown'}",
        "",
    ]
    for segment in segments:
        lines.append(f"[{_format_timestamp(segment['start'])}] {segment['text']}")
    return "\n".join(lines).strip() + "\n"


def _build_srt(segments: list[dict[str, Any]]) -> str:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    f"{_format_srt_time(segment['start'])} --> {_format_srt_time(segment['end'])}",
                    segment["text"],
                ]
            )
        )
    return "\n\n".join(blocks).strip() + "\n"


def _format_timestamp(seconds: float) -> str:
    total_seconds = max(int(seconds), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _format_srt_time(seconds: float) -> str:
    milliseconds = max(int(round(seconds * 1000)), 0)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _write_transcript_meta(
    item_dir: Path,
    result: TranscriptResult,
    *,
    model_size: str,
) -> None:
    meta_path = item_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["transcription"] = {
        "status": result.status,
        "engine": "faster-whisper",
        "model": model_size,
        "source_language": result.source_language,
        "transcript_path": _relative_path(item_dir, result.transcript_path),
        "original_srt_path": _relative_path(item_dir, result.original_srt_path),
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _relative_path(item_dir: Path, path: Path | None) -> str:
    if path is None:
        return ""
    return str(path.relative_to(item_dir))


def _load_cached_result(item_dir: Path) -> TranscriptResult | None:
    meta_path = item_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    transcription = meta.get("transcription") or {}
    if transcription.get("status") != "ready":
        return None

    transcript_path = _absolute_optional(item_dir, transcription.get("transcript_path"))
    original_srt_path = _absolute_optional(item_dir, transcription.get("original_srt_path"))
    required_paths = [transcript_path, original_srt_path]
    if not all(path and path.exists() for path in required_paths):
        return None
    return TranscriptResult(
        status="ready",
        source_language=transcription.get("source_language") or "",
        transcript_path=transcript_path,
        original_srt_path=original_srt_path,
    )


def _absolute_optional(item_dir: Path, path: str | None) -> Path | None:
    if not path:
        return None
    return item_dir / path
