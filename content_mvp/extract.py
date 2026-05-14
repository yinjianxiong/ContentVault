from __future__ import annotations

from html.parser import HTMLParser
from typing import Any


class PageExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.meta: dict[str, str] = {}
        self.links: list[dict[str, str]] = []
        self.images: list[str] = []
        self._tag_stack: list[str] = []
        self._title_parts: list[str] = []
        self._text_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        self._tag_stack.append(tag)

        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1

        if tag == "meta":
            key = attr.get("property") or attr.get("name")
            content = attr.get("content")
            if key and content:
                self.meta[key.lower()] = content.strip()

        if tag == "link":
            self.links.append(attr)

        if tag == "img" and attr.get("src"):
            self.images.append(attr["src"])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if not text:
            return
        if self._tag_stack and self._tag_stack[-1] == "title":
            self._title_parts.append(text)
        if self._skip_depth == 0 and len(text) > 1:
            self._text_parts.append(text)

    def result(self) -> dict[str, Any]:
        title = self._first(
            self.meta.get("og:title"),
            self.meta.get("twitter:title"),
            " ".join(self._title_parts).strip(),
        )
        description = self._first(
            self.meta.get("og:description"),
            self.meta.get("description"),
            self.meta.get("twitter:description"),
        )
        image = self._first(
            self.meta.get("og:image"),
            self.meta.get("twitter:image"),
            self.images[0] if self.images else "",
        )
        video = self._first(
            self.meta.get("og:video"),
            self.meta.get("og:video:url"),
            self.meta.get("twitter:player"),
        )
        text = self._clean_text(self._text_parts)
        return {
            "title": title,
            "description": description,
            "image": image,
            "video": video,
            "text": text,
            "meta": self.meta,
            "image_candidates": self.images[:30],
        }

    @staticmethod
    def _first(*values: str | None) -> str:
        for value in values:
            if value and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _clean_text(parts: list[str]) -> str:
        seen: set[str] = set()
        cleaned: list[str] = []
        for part in parts:
            if part in seen:
                continue
            seen.add(part)
            cleaned.append(part)
        return "\n".join(cleaned)


def extract_page(html: str) -> dict[str, Any]:
    parser = PageExtractor()
    parser.feed(html)
    return parser.result()

