from __future__ import annotations

from urllib.parse import urlparse


def detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "douyin.com" in host or "iesdouyin.com" in host:
        return "douyin"
    if "toutiao.com" in host or "snssdk.com" in host:
        return "toutiao"
    if "xiaohongshu.com" in host or "xhslink.com" in host:
        return "xiaohongshu"
    return host.replace("www.", "").split(":")[0] or "unknown"

