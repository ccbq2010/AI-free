"""RSS 订阅源抓取器。

通过 RSSHub 桥接中文社区（V2EX、少数派等），抓取含免费关键词的帖子。
"""

import feedparser
from . import RawCandidate, matches_keywords, AI_TOPIC_KEYWORDS
from .http import fetch_text

RSS_FEEDS = [
    # 量子位（AI 媒体主力，福利/额度文章首发地）
    ("qbitai", "https://www.qbitai.com/feed"),
    # IT之家 全量 RSS（含 AI 内容）
    ("ithome", "https://www.ithome.com/rss/"),
    # 少数派
    ("sspai", "https://sspai.com/feed"),
    # 机器之心 ⚠️ feed XML 不规范（mismatched tag），已加 bozo 容错
    ("jiqizhixin", "https://www.jiqizhixin.com/rss"),
]


def fetch_feed(source_id: str, url: str, keywords: list[str] | None = None) -> list[RawCandidate]:
    """抓取单个 RSS feed。

    keywords 默认用宽泛 AI 关键词（AI_TOPIC_KEYWORDS），LLM 抽取时会二次过滤。
    """
    candidates = []
    text = fetch_text(url)
    if text is None:
        return candidates

    feed = feedparser.parse(text)
    if feed.bozo and not feed.entries:
        print(f"    [WARN] {source_id} feed 解析失败: {feed.bozo_exception}")
        return candidates

    kws = keywords if keywords is not None else AI_TOPIC_KEYWORDS
    for entry in feed.entries[:30]:  # 只取最新 30 条
        title = entry.get("title", "")
        link = entry.get("link", "")
        summary = entry.get("summary", "")[:200]

        full_text = f"{title} {summary}"
        hit = [kw for kw in kws if kw.lower() in full_text.lower()]
        if not hit:
            continue

        candidates.append(RawCandidate(
            source=f"rss:{source_id}",
            name=title[:80],
            benefit=summary[:120],
            raw=full_text[:200],
            url=link,
            keywords=hit,
        ))

    return candidates


def fetch_all() -> list[RawCandidate]:
    """抓取所有 RSS 源（使用宽泛 AI 关键词，LLM 二次过滤）。"""
    all_candidates = []
    for source_id, url in RSS_FEEDS:
        print(f"  RSS: {source_id}")
        candidates = fetch_feed(source_id, url, keywords=AI_TOPIC_KEYWORDS)
        print(f"    Found {len(candidates)} candidates")
        all_candidates.extend(candidates)
    return all_candidates
