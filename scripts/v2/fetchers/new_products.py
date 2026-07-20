"""AI IDE / API 平台新品发布监控（v2 新增）。

新产品上线往往伴随新用户福利。监控渠道：
  - Product Hunt 当日 AI 类目（公开 GraphQL 需 token，退而用 RSS 桥/话题页）
  - GitHub Trending 中新增的 AI IDE / API 平台类仓库描述
  - 知名 AI 新品聚合 RSS（如 There's An AI For That 等，失败自动跳过）

产出的是「线索」级别候选，由 LLM 判断是否真有新用户福利。
"""

from __future__ import annotations

import re
from html import unescape

from .. import RawCandidate, is_new_user_benefit_candidate, matches_topic
from ..http_util import fetch_text

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_html(text: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", unescape(text or ""))).strip()


# ── Product Hunt（RSS 桥） ──────────────────────────────

def _fetch_producthunt() -> list[RawCandidate]:
    """Product Hunt 首页 RSS（通过 rsshub；不可达则跳过）。"""
    candidates: list[RawCandidate] = []
    for bridge in [
        "https://rsshub.app/producthunt/today",
    ]:
        xml = fetch_text(bridge, max_bytes=2 * 1024 * 1024)
        if xml is None:
            print(f"    [SKIP] producthunt bridge failed: {bridge}")
            continue
        try:
            import feedparser
        except ImportError:
            return candidates
        feed = feedparser.parse(xml)
        for entry in feed.entries[:30]:
            title = entry.get("title", "")
            summary = _clean_html(entry.get("summary", ""))
            link = entry.get("link", "")
            text = f"{title} {summary}"
            if not matches_topic(text):
                continue
            ok, white, _ = is_new_user_benefit_candidate(text)
            if not ok:
                continue
            candidates.append(RawCandidate(
                source="newproduct:producthunt",
                name=title[:60],
                benefit=summary[:120],
                raw=text[:300],
                url=link,
                keywords=white,
            ))
        print(f"    producthunt: {len(candidates)} candidates")
        break  # 一个桥成功就不再试下一个
    return candidates


# ── GitHub 搜索：新出现的 AI IDE / API 平台 ─────────────

def _fetch_github_new_repos() -> list[RawCandidate]:
    """搜索最近创建、描述含 AI IDE/API 且提到注册福利的仓库。"""
    candidates: list[RawCandidate] = []
    import json as _json
    from ..http_util import fetch

    # 近 90 天创建、stars>50、描述含福利词的 AI 平台仓库
    queries = [
        "AI+IDE+free+credits+created:>2026-04-01",
        "LLM+API+free+trial+created:>2026-04-01",
    ]
    for q in queries:
        url = (
            "https://api.github.com/search/repositories"
            f"?q={q}&sort=stars&order=desc&per_page=20"
        )
        data = fetch(url, max_bytes=1024 * 1024)
        if data is None:
            print(f"    [SKIP] github search failed: {q}")
            continue
        try:
            payload = _json.loads(data.decode("utf-8", errors="replace"))
        except _json.JSONDecodeError:
            continue
        for repo in payload.get("items", []):
            name = repo.get("full_name", "")
            desc = repo.get("description") or ""
            html_url = repo.get("html_url", "")
            text = f"{name} {desc}"
            ok, white, _ = is_new_user_benefit_candidate(text)
            if not ok:
                continue
            candidates.append(RawCandidate(
                source="newproduct:github",
                name=name[:60],
                benefit=desc[:120],
                raw=text[:300],
                url=html_url,
                keywords=white,
            ))
        print(f"    github search [{q[:30]}...]: cumulative {len(candidates)}")
    return candidates


def fetch_all() -> list[RawCandidate]:
    """抓取全部新品监控源。"""
    all_candidates: list[RawCandidate] = []
    all_candidates.extend(_fetch_producthunt())
    all_candidates.extend(_fetch_github_new_repos())
    return all_candidates
