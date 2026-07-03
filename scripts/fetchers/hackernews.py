"""Hacker News Algolia API 抓取器。

搜索含 "free AI credit/token" 等关键词的帖子。
API 文档：https://hn.algolia.com/api
"""

import urllib.parse
import json
from . import RawCandidate, matches_keywords
from .http import fetch

SEARCH_QUERIES = [
    "free AI credit",
    "free AI token",
    "free LLM API",
    "AI giveaway",
    "free GPU cloud",
]

TAGS = "story"  # 只搜帖子，不搜评论


def search_hn(query: str) -> list[dict]:
    """调用 Algolia API 返回 hits 列表。"""
    params = urllib.parse.urlencode({
        "query": query,
        "tags": TAGS,
        "hitsPerPage": 20,
    })
    url = f"https://hn.algolia.com/api/v1/search?{params}"
    data = fetch(url)
    if data is None:
        return []
    try:
        result = json.loads(data)
        hits = result.get("hits", [])
        # 客户端过滤低质量
        return [h for h in hits if h.get("points", 0) > 10]
    except Exception:
        return []


def fetch_all() -> list[RawCandidate]:
    """搜索所有查询词，合并去重。"""
    seen_ids = set()
    candidates = []

    for query in SEARCH_QUERIES:
        print(f"  HN search: {query}")
        hits = search_hn(query)
        count = 0
        for hit in hits:
            hnid = hit.get("objectID", "")
            if hnid in seen_ids:
                continue
            seen_ids.add(hnid)

            title = hit.get("title", "")
            url = hit.get("url", f"https://news.ycombinator.com/item?id={hnid}")
            text = f"{title} — {hit.get('author', '')} | {hit.get('points', 0)}pts"

            kws = matches_keywords(text)
            if not kws:
                kws = matches_keywords(title)
            if not kws:
                continue

            candidates.append(RawCandidate(
                source=f"hn:{query}",
                name=title[:80],
                benefit=f"HN {hit.get('points', 0)}pts / {hit.get('num_comments', 0)} comments",
                raw=text[:200],
                url=url,
                keywords=kws,
            ))
            count += 1

        print(f"    Found {count} candidates")

    return candidates
