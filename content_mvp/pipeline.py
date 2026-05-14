from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from .extract import extract_page
from .fetch import FetchResult, fetch_url, fetch_with_browser
from .items import resolve_item_title
from .media import try_download_media
from .platforms import detect_platform
from .summarize import build_summary


@dataclass
class ArchiveOptions:
    data_dir: str = "data"
    note: str = ""
    download_media: bool = False
    use_browser: bool = False
    cookies_from_browser: str = ""
    cookies_file: str = ""
    media_proxy: str | None = None


@dataclass
class ArchiveResult:
    item_dir: Path
    platform: str
    title: str
    media_download: dict[str, str]


def archive_link(url: str, options: ArchiveOptions) -> ArchiveResult:
    now = datetime.now()
    fetch = fetch_with_browser(url) if options.use_browser else fetch_url(url)
    platform = detect_platform(fetch.final_url or url)
    extracted = extract_page(fetch.html) if fetch.html else _empty_extract()
    slug = _make_slug(platform, extracted["title"], fetch.final_url or url)
    item_dir = Path(options.data_dir) / now.strftime("%Y-%m-%d") / slug
    media_dir = item_dir / "media"
    item_dir.mkdir(parents=True, exist_ok=True)

    raw_path = item_dir / "raw.html"
    raw_path.write_text(fetch.html, encoding="utf-8")
    if fetch.screenshot_png:
        (item_dir / "screenshot.png").write_bytes(fetch.screenshot_png)

    media_result = {}
    if options.download_media:
        media_result = try_download_media(
            fetch.final_url or url,
            media_dir,
            cookies_from_browser=options.cookies_from_browser,
            cookies_file=options.cookies_file,
            media_proxy=options.media_proxy,
        )

    meta = _build_meta(url, fetch, platform, extracted, options.note, media_result, now)
    (item_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (item_dir / "content.md").write_text(
        _build_content_markdown(meta, extracted),
        encoding="utf-8",
    )
    (item_dir / "summary.md").write_text(
        build_summary(meta, extracted, title=resolve_item_title(item_dir, meta)),
        encoding="utf-8",
    )

    return ArchiveResult(
        item_dir=item_dir,
        platform=platform,
        title=extracted["title"],
        media_download=media_result,
    )


def _build_meta(
    url: str,
    fetch: FetchResult,
    platform: str,
    extracted: dict,
    note: str,
    media_result: dict,
    now: datetime,
) -> dict:
    return {
        "archived_at": now.isoformat(timespec="seconds"),
        "platform": platform,
        "requested_url": url,
        "final_url": fetch.final_url,
        "http_status": fetch.status,
        "content_type": fetch.content_type,
        "fetch_error": fetch.error,
        "title": extracted["title"],
        "description": extracted["description"],
        "image": extracted["image"],
        "video": extracted["video"],
        "image_candidates": extracted["image_candidates"],
        "note": note,
        "media_download": media_result,
    }


def _build_content_markdown(meta: dict, extracted: dict) -> str:
    lines = [
        f"# {meta['title'] or '未提取到标题'}",
        "",
        f"- 平台: {meta['platform']}",
        f"- 原始链接: {meta['requested_url']}",
        f"- 最终链接: {meta['final_url']}",
        f"- 归档时间: {meta['archived_at']}",
    ]
    if meta.get("note"):
        lines.append(f"- 个人备注: {meta['note']}")
    if meta.get("description"):
        lines.extend(["", "## 页面描述", "", meta["description"]])
    if meta.get("image"):
        lines.extend(["", "## 封面/主图线索", "", meta["image"]])
    if meta.get("video"):
        lines.extend(["", "## 视频线索", "", meta["video"]])

    body = extracted.get("text", "").strip()
    lines.extend(["", "## 提取正文", ""])
    lines.append(body if body else "未提取到正文。可以尝试加 `--browser` 重新归档动态页面。")
    return "\n".join(lines).strip() + "\n"


def _empty_extract() -> dict:
    return {
        "title": "",
        "description": "",
        "image": "",
        "video": "",
        "text": "",
        "meta": {},
        "image_candidates": [],
    }


def _make_slug(platform: str, title: str, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    source = title or urlparse(url).path.strip("/") or "link"
    source = re.sub(r"https?://", "", source)
    source = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", source, flags=re.UNICODE)
    source = source.strip("-").lower()[:48] or "link"
    return f"{platform}_{source}_{digest}"
