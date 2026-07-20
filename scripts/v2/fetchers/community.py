"""中文社区羊毛帖抓取器（v2 新增）。

信息源：
  - V2EX 最近主题（官方 JSON API，公开无需鉴权）
  - 少数派 RSS
  - 知乎通过 RSS 桥（rsshub 公共实例；不可达时自动跳过，不影响整体）

策略：先用泛 AI 话题词粗筛，再用 v2 白名单精筛，降低噪音。
"""

from __future__ import annotations

import json
import re
from html import unescape

from .. import RawCandidate, is_new_user_benefit_candidate, matches_topic
from ..http_util import fetch, fetch_text

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_html(text: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", unescape(text or ""))).strip()


# ── V2EX ────────────────────────────────────────────────

def _fetch_v2ex() -> list[RawCandidate]:
    """拉取 V2EX 最新主题，筛 AI 话题 + 福利白名单。"""
    candidates: list[RawCandidate] = []
    data = fetch("https://www.v2ex.com/api/topics/latest.json", max_bytes=1024 * 1024)
    if data is None:
        print("    [SKIP] v2ex api failed")
        return candidates
    try:
        topics = json.loads(data.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        print("    [SKIP] v2ex api returned non-JSON")
        return candidates

    for t in topics:
        title = t.get("title", "")
        content = _clean_html(t.get("content", ""))
        url = t.get("url", "")
        text = f"{title} {content}"
        # 必须同时命中 AI 话题 + 福利白名单
        if not matches_topic(text):
            continue
        ok, white, _ = is_new_user_benefit_candidate(text)
        if not ok:
            continue
        candidates.append(RawCandidate(
            source="community:v2ex",
            name=title[:60],
            benefit=content[:120] or title[:120],
            raw=text[:300],
            url=url,
            keywords=white,
        ))
    print(f"    v2ex: {len(candidates)} candidates")
    return candidates


# ── RSS 通用（少数派 / 知乎桥） ─────────────────────────

def _fetch_rss(url: str, source: str, limit: int = 40) -> list[RawCandidate]:
    """解析 RSS/Atom，筛 AI 话题 + 福利白名单。"""
    candidates: list[RawCandidate] = []
    xml = fetch_text(url, max_bytes=2 * 1024 * 1024)
    if xml is None:
        print(f"    [SKIP] {source} rss failed")
        return candidates

    try:
        import feedparser
    except ImportError:
        print("    [SKIP] feedparser not installed")
        return candidates

    feed = feedparser.parse(xml)
    for entry in feed.entries[:limit]:
        title = entry.get("title", "")
        summary = _clean_html(entry.get("summary", "") or entry.get("description", ""))
        link = entry.get("link", "")
        text = f"{title} {summary}"
        if not matches_topic(text):
            continue
        ok, white, _ = is_new_user_benefit_candidate(text)
        if not ok:
            continue
        candidates.append(RawCandidate(
            source=f"community:{source}",
            name=title[:60],
            benefit=summary[:120] or title[:120],
            raw=text[:300],
            url=link,
            keywords=white,
        ))
    print(f"    {source}: {len(candidates)} candidates")
    return candidates


def fetch_all() -> list[RawCandidate]:
    """抓取全部社区源。单源失败不影响其他源。"""
    all_candidates: list[RawCandidate] = []

    all_candidates.extend(_fetch_v2ex())
    all_candidates.extend(_fetch_rss("https://sspai.com/feed", "sspai"))
    # 知乎搜索 RSS 桥（公共实例不稳定，失败自动跳过）
    all_candidates.extend(_fetch_rss(
        "https://rsshub.app/zhihu/search/AI%20邀请码", "zhihu"))

    return all_candidates
