from __future__ import annotations

import re


def build_summary(meta: dict, extracted: dict, *, title: str = "") -> str:
    title = title or meta.get("title") or "未提取到标题"
    description = meta.get("description") or ""
    text = extracted.get("text", "")
    paragraphs = _important_paragraphs(text)
    keywords = _keywords(" ".join([title, description, text]))

    one_line = description or (paragraphs[0] if paragraphs else title)
    one_line = _clip(one_line, 140)

    lines = [
        f"# 二创分析: {title}",
        "",
        "## 一句话总结",
        "",
        one_line or "内容较少，建议先人工补充视频文案或正文。",
        "",
        "## 核心信息",
        "",
    ]
    if paragraphs:
        lines.extend(f"- {_clip(item, 120)}" for item in paragraphs[:5])
    else:
        lines.append("- 暂未提取到足够正文。可以查看 `raw.html` 或用 `--browser` 重新抓取。")

    lines.extend(
        [
            "",
            "## 可能的爆点",
            "",
            f"- 关键词: {', '.join(keywords[:10]) if keywords else '待人工补充'}",
            "- 关注冲突点: 谁受益、谁受损、为什么现在发生、普通人和它有什么关系。",
            "- 关注情绪点: 新鲜感、反常识、焦虑、共鸣、爽点或实用价值。",
            "",
            "## 可二创角度",
            "",
            "- 信息压缩: 用更短的结构讲清楚原内容。",
            "- 观点补充: 加入自己的判断、案例或反例。",
            "- 场景转译: 把内容改成普通人更容易代入的生活/工作场景。",
            "- 清单化: 拆成步骤、避坑、误区或行动建议。",
            "",
            "## 标题方向",
            "",
            f"- {title}",
            "- 这件事真正值得关注的不是表面，而是背后的变化",
            "- 普通人看懂这点，就知道下一步该怎么做",
            "",
            "## 风险提醒",
            "",
            "- 二创时尽量避免照搬原文表达和完整结构。",
            "- 涉及事实、数据、人物评价时，发布前需要二次核验。",
            "- 平台内容可能有版权或转载限制，建议只做观点化、结构化再表达。",
            "",
            "## 改写脚本骨架",
            "",
            "1. 开场: 用一句话点出反常识或冲突。",
            "2. 背景: 交代这条内容说了什么。",
            "3. 拆解: 分 2-3 点解释为什么值得关注。",
            "4. 观点: 加入你的判断或经验。",
            "5. 收尾: 给一个行动建议或开放问题。",
            "",
            "## 原始链接",
            "",
            meta.get("final_url") or meta.get("requested_url") or "",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def _important_paragraphs(text: str) -> list[str]:
    candidates = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if 20 <= len(line) <= 220:
            candidates.append(line)
    return candidates[:8]


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}", text)
    stop = {
        "一个",
        "我们",
        "你们",
        "他们",
        "这个",
        "那个",
        "没有",
        "什么",
        "因为",
        "所以",
        "the",
        "and",
        "for",
        "with",
    }
    counts: dict[str, int] = {}
    for word in words:
        key = word.lower()
        if key in stop:
            continue
        counts[key] = counts.get(key, 0) + 1
    return [word for word, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)]


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."
