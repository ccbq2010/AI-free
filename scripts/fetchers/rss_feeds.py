"""RSS 订阅源抓取器。

通过 RSSHub 桥接中文社区（V2EX、少数派等），抓取含免费关键词的帖子。
"""

import feedparser
from . import RawCandidate, matches_keywords
from .http import fetch_text

RSS_FEEDS = [
    # IT之家 全量 RSS（含 AI 内容，2026-07 验证可达）
    ("ithome", "https://www.ithome.com/rss/"),
    # 少数派
    ("sspai", "https://sspai.com/feed"),
]


def fetch_feed(source_id: str, url: str) -> list[RawCandidate]:
    """抓取单个 RSS feed。"""
    candidates = []
    text = fetch_text(url)
    if text is None:
        return candidates

    feed = feedparser.parse(text)
    for entry in feed.entries[:30]:  # 只取最新 30 条
        title = entry.get("title", "")
        link = entry.get("link", "")
        summary = entry.get("summary", "")[:200]

        full_text = f"{title} {summary}"
        kws = matches_keywords(full_text)
        if not kws:
            continue

        candidates.append(RawCandidate(
            source=f"rss:{source_id}",
            name=title[:80],
            benefit=summary[:120],
            raw=full_text[:200],
            url=link,
            keywords=kws,
        ))

    return candidates


def fetch_all() -> list[RawCandidate]:
    """抓取所有 RSS 源。"""
    all_candidates = []
    for source_id, url in RSS_FEEDS:
        print(f"  RSS: {source_id}")
        candidates = fetch_feed(source_id, url)
        print(f"    Found {len(candidates)} candidates")
        all_candidates.extend(candidates)
    return all_candidates
