from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path


def try_download_media(
    url: str,
    media_dir: Path,
    *,
    cookies_from_browser: str = "",
    cookies_file: str = "",
    media_proxy: str | None = None,
) -> dict[str, str]:
    yt_dlp = shutil.which("yt-dlp")
    if not yt_dlp:
        return {
            "status": "skipped",
            "reason": "yt-dlp is not installed",
        }

    media_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(media_dir / "%(title).120s-%(id)s.%(ext)s")
    command = [
        yt_dlp,
        "--no-playlist",
        "--write-info-json",
        "--write-thumbnail",
        "-o",
        output_template,
    ]
    if cookies_from_browser:
        command.extend(["--cookies-from-browser", cookies_from_browser])
    if cookies_file:
        command.extend(["--cookies", cookies_file])
    if media_proxy is not None:
        command.extend(["--proxy", media_proxy])
    command.append(url)
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        timeout=180,
    )
    return {
        "status": "ok" if completed.returncode == 0 else "failed",
        "returncode": str(completed.returncode),
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def summarize_media_download(result: dict[str, str]) -> str:
    status = result.get("status", "")
    if status == "ok":
        return "媒体下载成功"
    if status == "skipped":
        return f"媒体下载已跳过: {result.get('reason', 'unknown reason')}"
    if status == "failed":
        message = (result.get("stderr") or result.get("stdout") or "").strip()
        last_line = message.splitlines()[-1] if message else "unknown error"
        return f"媒体下载失败: {last_line}"
    return ""


def open_in_downie(url: str, app_name: str = "Downie 4") -> dict[str, str]:
    completed = subprocess.run(
        ["open", "-a", app_name, url],
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )
    return {
        "status": "ok" if completed.returncode == 0 else "failed",
        "returncode": str(completed.returncode),
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def import_recent_downloaded_media(
    downloads_dir: Path,
    media_dir: Path,
    *,
    since_timestamp: float,
    timeout_seconds: int,
) -> dict[str, str]:
    if timeout_seconds <= 0:
        return {"status": "skipped", "reason": "downie wait disabled"}

    deadline = time.time() + timeout_seconds
    seen_sizes: dict[Path, int] = {}
    suffixes = {".mp4", ".mov", ".m4v", ".webm"}

    while time.time() <= deadline:
        candidates = [
            path
            for path in downloads_dir.glob("*")
            if path.is_file()
            and path.suffix.lower() in suffixes
            and path.stat().st_mtime >= since_timestamp
        ]
        candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for source in candidates:
            size = source.stat().st_size
            if size <= 0:
                continue
            if seen_sizes.get(source) != size:
                seen_sizes[source] = size
                continue

            media_dir.mkdir(parents=True, exist_ok=True)
            destination = media_dir / source.name
            shutil.copy2(source, destination)
            return {
                "status": "imported",
                "source": "Downie 4",
                "path": str(destination.relative_to(media_dir.parent)),
                "original_path": str(source),
            }
        time.sleep(2)

    return {
        "status": "not_found",
        "reason": f"No completed media file appeared in {downloads_dir}",
    }
