"""中文科技媒体 RSS/聚合抓取器。

覆盖可在中国大陆 GitHub Actions 中直连访问的源：
  - iTHome 全量 RSS（含 AI 内容，2026-07 验证可达）
  - 少数派 RSS
  - 机器之心 RSS

不覆盖（在国内 CI 环境中无法稳定访问）：
  - 小红书 / 微信公众号：需登录 Cookie
  - B站：需 wbi 信号或 UA 反爬
  - Reddit / HackerNews：国际出口波动

微信公众号和小红书的候选可通过 GitHub Issues 手工登记，
或部署到能直连的 runner（如香港的第三方服务器）。
"""

from . import RawCandidate, matches_keywords
from .http import fetch_text

SOURCES = [
    ("ithome", "https://www.ithome.com/rss/"),
    ("sspai", "https://sspai.com/feed"),
    ("jiqizhixin", "https://www.jiqizhixin.com/rss"),
]


def fetch_feed(source_id: str, url: str) -> list[RawCandidate]:
    """抓取单个 RSS/Atom feed，提取含免费关键词的条目。"""
    candidates = []
    text = fetch_text(url)
    if text is None:
        return candidates

    import feedparser
    feed = feedparser.parse(text)
    for entry in feed.entries[:50]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        summary = entry.get("summary", "")[:200]
        full = f"{title} {summary}"
        kws = matches_keywords(full)
        if not kws:
            continue
        candidates.append(RawCandidate(
            source=f"zh_rss:{source_id}",
            name=title[:80],
            benefit=summary[:120],
            raw=full[:200],
            url=link,
            keywords=kws,
        ))
    return candidates


def fetch_all() -> list[RawCandidate]:
    """抓取所有中文媒体源。"""
    all_candidates = []
    for source_id, url in SOURCES:
        print(f"  Chinese RSS: {source_id}")
        try:
            candidates = fetch_feed(source_id, url)
            print(f"    Found {len(candidates)} candidates")
            all_candidates.extend(candidates)
        except Exception as e:
            print(f"    [WARN] {source_id} failed: {e}")
    return all_candidates
