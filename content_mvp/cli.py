from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .analyze import analyze_archive, analyze_item
from .items import resolve_item_title
from .media import (
    import_recent_downloaded_media,
    open_in_downie,
    summarize_media_download,
    update_media_download_meta,
)
from .nocobase import build_processed_asset_payload
from .obsidian import export_to_obsidian
from .pipeline import ArchiveOptions, archive_link


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="content-mvp",
        description="Archive a link locally and generate a creator-friendly summary draft.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="Archive one link")
    add.add_argument("url", help="The copied link to archive")
    add.add_argument("--note", default="", help="Optional personal note for this item")
    add.add_argument(
        "--data-dir",
        default="data",
        help="Archive root directory. Defaults to ./data",
    )
    add.add_argument(
        "--download-media",
        action="store_true",
        help="Try to download media with yt-dlp if it is installed locally",
    )
    add.add_argument(
        "--cookies-from-browser",
        default="",
        metavar="BROWSER",
        help=(
            "Pass browser cookies to yt-dlp, e.g. chrome, safari, firefox, "
            "or 'chrome:Profile 1'. Useful for Douyin and other logged-in pages."
        ),
    )
    add.add_argument(
        "--cookies-file",
        default="",
        metavar="PATH",
        help="Pass a Netscape cookies.txt file to yt-dlp",
    )
    add.add_argument(
        "--media-proxy",
        default=None,
        metavar="URL",
        help="Pass a proxy URL to yt-dlp for media downloads",
    )
    add.add_argument(
        "--no-media-proxy",
        action="store_true",
        help="Disable proxy use for yt-dlp media downloads",
    )
    add.add_argument(
        "--browser",
        action="store_true",
        help="Try to render the page with Playwright if it is installed locally",
    )
    add.add_argument(
        "--open-downie",
        action="store_true",
        help="Open the URL in Downie 4 after archiving",
    )
    add.add_argument(
        "--downie-wait",
        type=int,
        default=180,
        metavar="SECONDS",
        help="When using --open-downie, wait for a new media file in ~/Downloads and import it. Defaults to 180.",
    )

    inspect = subparsers.add_parser("inspect", help="Inspect archived items")
    inspect.add_argument("path", help="An item directory or a day directory")

    export_obsidian = subparsers.add_parser(
        "export-obsidian",
        help="Export archived items to Obsidian markdown notes",
    )
    export_obsidian.add_argument("path", help="An item directory or a day directory")
    export_obsidian.add_argument(
        "--vault",
        required=True,
        help="Obsidian target folder or vault path",
    )

    analyze = subparsers.add_parser(
        "analyze",
        help="Refresh summaries and create a Codex analysis packet for archived items",
    )
    analyze.add_argument("path", help="An item directory or a day directory")
    analyze.add_argument(
        "--frames",
        type=int,
        default=6,
        help="Number of video frames to sample into analysis/frames. Defaults to 6.",
    )
    analyze.add_argument(
        "--export-obsidian",
        default="",
        metavar="VAULT",
        help="Optionally export analyzed items to an Obsidian folder after analysis.",
    )

    nocobase_payload = subparsers.add_parser(
        "nocobase-payload",
        help="Print processed_assets JSON payloads for archived items",
    )
    nocobase_payload.add_argument("path", help="An item directory or a day directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "add":
        options = ArchiveOptions(
            data_dir=args.data_dir,
            note=args.note,
            download_media=args.download_media,
            use_browser=args.browser,
            cookies_from_browser=args.cookies_from_browser,
            cookies_file=args.cookies_file,
            media_proxy="" if args.no_media_proxy else args.media_proxy,
        )
        result = archive_link(args.url, options)
        print(f"已归档: {result.item_dir}")
        print(f"标题: {result.title or '未提取到标题'}")
        print(f"平台: {result.platform}")
        media_message = summarize_media_download(result.media_download)
        if media_message:
            print(media_message)
            if result.media_download.get("status") == "failed":
                browser = args.cookies_from_browser or "chrome"
                print(
                    "提示: 这类链接常需要登录态，可以重试 "
                    f"`--download-media --cookies-from-browser {browser}`。"
                )
        if args.open_downie:
            downie_started_at = time.time()
            downie_result = open_in_downie(args.url)
            if downie_result["status"] == "ok":
                print("已发送到 Downie 4")
                import_result = import_recent_downloaded_media(
                    Path.home() / "Downloads",
                    result.item_dir / "media",
                    since_timestamp=downie_started_at,
                    timeout_seconds=args.downie_wait,
                )
                if import_result["status"] == "imported":
                    update_media_download_meta(result.item_dir, import_result)
                    analyze_item(result.item_dir)
                    print(f"已导入媒体: {result.item_dir / import_result['path']}")
                elif import_result["status"] == "not_found":
                    print(f"未自动导入媒体: {import_result['reason']}")
            else:
                print(
                    "发送到 Downie 4 失败: "
                    f"{downie_result.get('stderr') or downie_result.get('stdout')}"
                )
        print(f"总结: {result.item_dir / 'summary.md'}")
        return 0

    if args.command == "inspect":
        for item_dir in _iter_item_dirs(Path(args.path)):
            meta_path = item_dir / "meta.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            print(f"{item_dir}")
            print(f"  标题: {resolve_item_title(item_dir, meta)}")
            print(f"  平台: {meta.get('platform') or ''}")
            print(f"  链接: {meta.get('final_url') or meta.get('requested_url') or ''}")
        return 0

    if args.command == "analyze":
        results = analyze_archive(Path(args.path), frame_count=args.frames)
        for result in results:
            print(f"已分析: {result.item_dir}")
            print(f"  标题: {result.title}")
            print(f"  总结: {result.summary_path}")
            print(f"  Codex 分析包: {result.brief_path}")
            if result.frame_paths:
                print(f"  抽帧: {len(result.frame_paths)} 张")
        if args.export_obsidian:
            notes = export_to_obsidian(Path(args.path), Path(args.export_obsidian))
            for note in notes:
                print(f"已导出: {note}")
            print(f"共导出 {len(notes)} 条笔记")
        return 0

    if args.command == "export-obsidian":
        notes = export_to_obsidian(Path(args.path), Path(args.vault))
        for note in notes:
            print(f"已导出: {note}")
        print(f"共导出 {len(notes)} 条笔记")
        return 0

    if args.command == "nocobase-payload":
        payloads = [
            build_processed_asset_payload(item_dir)
            for item_dir in _iter_item_dirs(Path(args.path))
        ]
        print(json.dumps(payloads, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


def _iter_item_dirs(path: Path) -> list[Path]:
    if (path / "meta.json").exists():
        return [path]
    return sorted(parent for parent in path.iterdir() if (parent / "meta.json").exists())


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
