"""GitHub 仓库抓取器。

通过 GitHub REST API /search/repositories 发现中文友好的免费 AI 聚合
仓库。相比直连 GitHub Topic 页面（依赖 JS 渲染），REST API 在
GitHub Actions 中稳定可用，无需额外配置。

限定搜索范围：
  - 中文聚合仓库（描述含「免费」「白嫖」「福利」「token」「免费」等）
  - 每仓库 ≥ 100 stars（噪声过滤）
"""

import json
from . import RawCandidate, matches_keywords
from .http import fetch

SEARCH_QUERIES = [
    "免费 AI 福利 stars:>100",
    "白嫖 token stars:>100",
    "free chatgpt stars:>500",
    "AI 聚合 推荐 stars:>200",
]


def search_repos(query: str) -> list[dict]:
    """调用 GitHub Search API 返回 items 列表。"""
    import urllib.parse
    params = urllib.parse.urlencode({
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": 15,
    })
    url = f"https://api.github.com/search/repositories?{params}"
    data = fetch(url)
    if data is None:
        return []
    try:
        return json.loads(data).get("items", [])
    except Exception:
        return []


def fetch_all() -> list[RawCandidate]:
    """搜索所有查询词，合并去重。"""
    seen_ids = set()
    candidates = []

    for query in SEARCH_QUERIES:
        print(f"  GitHub API search: {query}")
        items = search_repos(query)
        count = 0
        for item in items:
            repo_id = item.get("full_name", "")
            if repo_id in seen_ids:
                continue
            seen_ids.add(repo_id)

            desc = item.get("description", "") or ""
            stars = item.get("stargazers_count", 0)
            lang = item.get("language", "")
            top_topic = (item.get("topics") or [""])[0]

            full_text = f"{repo_id} {desc} {top_topic} {lang}"
            kws = matches_keywords(full_text)
            if not kws and stars < 2000:
                continue  # 没有免费关键词且不够火则跳过

            candidates.append(RawCandidate(
                source=f"gh_api:{query}",
                name=repo_id[:80],
                benefit=f"★{stars} | {desc[:100]}",
                raw=full_text[:200],
                url=item.get("html_url", f"https://github.com/{repo_id}"),
                keywords=kws or ["free"],
            ))
            count += 1
        print(f"    Found {count} candidates")

    return candidates
