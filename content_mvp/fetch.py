from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    status: int | None
    content_type: str
    html: str
    error: str
    screenshot_png: bytes = b""


def fetch_url(url: str, timeout: int = 20) -> FetchResult:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            content_type = response.headers.get("content-type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            html = body.decode(charset, errors="replace")
            return FetchResult(
                requested_url=url,
                final_url=response.geturl(),
                status=response.status,
                content_type=content_type,
                html=html,
                error="",
            )
    except urllib.error.HTTPError as exc:
        body = exc.read()
        html = body.decode("utf-8", errors="replace") if body else ""
        return FetchResult(url, exc.geturl(), exc.code, "", html, str(exc))
    except Exception as exc:  # noqa: BLE001 - archive errors should be recorded.
        return FetchResult(url, url, None, "", "", str(exc))


def fetch_with_browser(url: str, timeout_ms: int = 20000) -> FetchResult:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        return FetchResult(url, url, None, "", "", f"Playwright unavailable: {exc}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent=USER_AGENT,
                locale="zh-CN",
                viewport={"width": 1440, "height": 1200},
            )
            response = page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            html = page.content()
            screenshot = page.screenshot(full_page=True)
            final_url = page.url
            status = response.status if response else None
            content_type = response.headers.get("content-type", "") if response else ""
            browser.close()
            return FetchResult(url, final_url, status, content_type, html, "", screenshot)
    except Exception as exc:  # noqa: BLE001
        return FetchResult(url, url, None, "", "", str(exc))
