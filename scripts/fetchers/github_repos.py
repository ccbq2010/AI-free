"""GitHub 聚合仓库抓取器。

扫描多个已知聚合仓库的 README，提取含免费关键词的条目。
"""

import re
from . import RawCandidate, matches_keywords
from .http import fetch_text

# 已知聚合仓库列表（owner/repo 格式）—— 只保留确认存在的
AGGREGATOR_REPOS = [
    "xx025/carrot",
    "LiLittleCat/awesome-free-chatgpt",
]

# 匹配 README 中的列表项：- name: description 或 - name — description
_LIST_ITEM_RE = re.compile(
    r'^\s*[-*]\s+'           # 列表标记
    r'(.+?)[：:—\-–]\s+'     # 名称 + 分隔符
    r'(.+?)$',               # 描述
    re.MULTILINE,
)

# 也匹配纯链接行：- [name](url) — description
_LINK_ITEM_RE = re.compile(
    r'^\s*[-*]\s+'
    r'\[(.+?)\]\((.+?)\)\s*'
    r'[：:—\-–]?\s*'
    r'(.+?)$',
    re.MULTILINE,
)


def fetch_repo_readme(owner_repo: str) -> str | None:
    """获取仓库 README 内容。"""
    for branch in ["main", "master"]:
        url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/README.md"
        text = fetch_text(url)
        if text is not None:
            return text
    return None


def parse_readme(text: str, source: str) -> list[RawCandidate]:
    """从 README 文本中提取候选条目。"""
    candidates = []

    # 先尝试匹配带链接的列表项
    for m in _LINK_ITEM_RE.finditer(text):
        name, url, desc = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        line = f"- {name}: {desc}"
        kws = matches_keywords(line)
        if kws:
            candidates.append(RawCandidate(
                source=source,
                name=name[:60],
                benefit=desc[:120],
                raw=line[:200],
                url=url,
                keywords=kws,
            ))

    # 再匹配普通列表项
    for m in _LIST_ITEM_RE.finditer(text):
        name, desc = m.group(1).strip(), m.group(2).strip()
        line = f"- {name}: {desc}"
        kws = matches_keywords(line)
        if kws:
            # 避免与链接项重复
            if not any(c.raw == line[:200] for c in candidates):
                candidates.append(RawCandidate(
                    source=source,
                    name=name[:60],
                    benefit=desc[:120],
                    raw=line[:200],
                    keywords=kws,
                ))

    return candidates


def fetch_all() -> list[RawCandidate]:
    """抓取所有聚合仓库。"""
    all_candidates = []
    for repo in AGGREGATOR_REPOS:
        source = f"github:{repo}"
        print(f"  Fetching {repo}...")
        text = fetch_repo_readme(repo)
        if text is None:
            print(f"    [SKIP] README not found")
            continue
        candidates = parse_readme(text, source)
        print(f"    Found {len(candidates)} candidates")
        all_candidates.extend(candidates)
    return all_candidates
