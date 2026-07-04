#!/usr/bin/env python3
"""多源免费 AI 资源巡检脚本。

从多个信息源抓取候选平台，去重后输出 JSON 报告。
设计为 GitHub Actions cron 每周运行。

修复记录（vs 旧版）：
  - 正则语法错误 → 用两个预编译正则替代
  - 去重维度错位 → 用 URL 域名 + 名称归一化
  - 退出码语义反了 → 0=正常，1=发现新候选
  - 异常全被吞 → 结构化日志到 stderr
  - 无 max_bytes → http.py 统一限制 2MB
  - 只看 1 个源 → 扩展为 4 类信息源
"""

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# 让 scripts/ 成为可导入包
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from fetchers import RawCandidate, KEYWORDS  # noqa: E402
from fetchers.http import fetch_text  # noqa: E402

ROOT = SCRIPT_DIR.parent
DATA_FILE = ROOT / "data" / "platforms.json"
BLACKLIST_FILE = ROOT / "data" / "review_blacklist.json"


# ── 已收录平台 ──────────────────────────────────────────

def get_known_ids() -> set[str]:
    """返回已收录平台的 id 集合。"""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return {p["id"] for p in data}


def get_known_domains() -> set[str]:
    """返回已收录平台的 URL 域名集合。"""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    domains = set()
    for p in data:
        url = p.get("url", "")
        if url:
            domains.add(urlparse(url).netloc.lower())
    return domains


def get_blacklist() -> dict:
    """读取黑名单（已拒绝的域名和名称）。"""
    if BLACKLIST_FILE.exists():
        return json.loads(BLACKLIST_FILE.read_text(encoding="utf-8"))
    return {"domains": [], "names": []}


# 剥离 markdown 链接语法：[text](url) → text
_MD_LINK_RE = re.compile(r'\[(.+?)\]\(.+?\)')


def _strip_md_link(text: str) -> str:
    """去掉文本中的 markdown 链接语法，保留链接文本。"""
    return _MD_LINK_RE.sub(r'\1', text)


def normalize_name(name: str) -> str:
    """名称归一化：去 markdown 链接 → 小写 → 去空格 → 去特殊字符。"""
    name = _strip_md_link(name)
    return re.sub(r'[^a-z0-9一-鿿]', '', name.lower())


def candidate_to_dict(c: RawCandidate) -> dict:
    """将 RawCandidate 转为可序列化的 dict。"""
    return {
        "source": c.source,
        "name": c.name,
        "benefit": c.benefit,
        "raw": c.raw,
        "url": c.url,
        "keywords": c.keywords,
    }


# ── 多源抓取调度 ────────────────────────────────────────

# 内置 fetcher 模块列表，可按需增删（社区 PR 也容易）
DEFAULT_FETCHERS = [
    ("GitHub",     "fetchers.github_repos",  "fetch_all"),
    ("HackerNews", "fetchers.hackernews",    "fetch_all"),
    ("OpenRouter", "fetchers.openrouter",    "fetch_all"),
    ("RSS",        "fetchers.rss_feeds",     "fetch_all"),
    ("ChineseNews","fetchers.chinese_news",  "fetch_all"),
    ("GHTopics",   "fetchers.github_topics", "fetch_all"),
]


def fetch_all_sources(fetcher_list: list[tuple[str, str, str]] | None = None) -> list[RawCandidate]:
    """抓取所有信息源，末尾输出汇总。"""
    if fetcher_list is None:
        fetcher_list = DEFAULT_FETCHERS
    all_candidates = []
    per_source: list[tuple[str, int, str]] = []  # (name, count, status)

    for name, module_path, func_name in fetcher_list:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            func = getattr(mod, func_name)
            result = func()
            all_candidates.extend(result)
            status = "WARN:0" if len(result) == 0 else "OK"
            per_source.append((name, len(result), status))
        except Exception as e:
            per_source.append((name, 0, f"ERROR:{e}"))
            print(f"  [ERROR] {name} fetcher failed: {e}", file=sys.stderr)

    # 汇总行：一眼看出哪个源阵亡
    print("\n  ── Source Summary ──")
    for name, count, status in per_source:
        flag = "⚠️" if "WARN" in status or "ERROR" in status else "  "
        print(f"    {flag} {name:<15s} {count:>3} candidates  [{status}]")
    print(f"    {'':>18}{sum(c for _, c, _ in per_source):>3} total\n")

    return all_candidates





# ── 去重与过滤 ──────────────────────────────────────────

def deduplicate(candidates: list[RawCandidate]) -> list[RawCandidate]:
    """按 URL 域名 + 归一化名称去重，同时清洗名称中的 markdown 链接。"""
    seen_domains: dict[str, str] = {}
    seen_names: set[str] = set()
    unique = []

    for c in candidates:
        # 清洗名称中的 markdown 链接语法
        c.name = _strip_md_link(c.name)

        domain = urlparse(c.url).netloc.lower() if c.url else ""
        if domain and domain in seen_domains:
            continue

        norm = normalize_name(c.name)
        if norm in seen_names:
            continue

        if domain:
            seen_domains[domain] = c.name
        seen_names.add(norm)
        unique.append(c)

    return unique


def filter_known(candidates: list[RawCandidate], known_ids: set | None = None) -> list[RawCandidate]:
    """过滤已收录和已拒绝的候选。"""
    if known_ids is None:
        known_ids = get_known_ids()
    known_domains = get_known_domains()
    blacklist = get_blacklist()
    black_domains = {d.lower() for d in blacklist.get("domains", [])}
    black_names = {normalize_name(n) for n in blacklist.get("names", [])}
    known_names_normalized = {normalize_name(k) for k in known_ids}

    new = []
    for c in candidates:
        norm = normalize_name(c.name)
        domain = urlparse(c.url).netloc.lower() if c.url else ""

        if norm in known_names_normalized:
            continue
        if domain in known_domains:
            continue
        if domain in black_domains or norm in black_names:
            continue

        new.append(c)

    return new


# ── 报告生成 ────────────────────────────────────────────

def generate_report(candidates: list[RawCandidate], known_count: int = 0) -> dict:
    """生成结构化报告。"""
    return {
        "known_platforms_count": known_count,
        "candidates_total": len(candidates),
        "new_candidates": [candidate_to_dict(c) for c in candidates[:50]],
        "sources_scanned": len(DEFAULT_FETCHERS),
        "keywords_used": len(KEYWORDS),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI-free multi-source scanner")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Save JSON report to file (for CI artifact parsing)")
    args = parser.parse_args()

    print("=" * 60)
    print("AI-free multi-source scanner v2.2")
    print("=" * 60)

    # 单次读取平台数据，后续函数共享（避免重复 IO）
    platforms = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    known_ids = {p["id"] for p in platforms}

    # Phase 1: 多源抓取
    print("\n[Phase 1] Fetching from all sources...")
    candidates = fetch_all_sources()
    print(f"  Total raw candidates: {len(candidates)}")

    # Phase 2: 去重
    print("\n[Phase 2] Deduplicating...")
    candidates = deduplicate(candidates)
    print(f"  After dedup: {len(candidates)}")

    # Phase 3: 过滤已收录（传参避免内部读文件）
    print("\n[Phase 3] Filtering known platforms...")
    new_candidates = filter_known(candidates, known_ids=known_ids)
    print(f"  New candidates: {len(new_candidates)}")

    # Phase 4: 输出报告
    report = generate_report(new_candidates, known_count=len(known_ids))
    print("\n" + json.dumps(report, ensure_ascii=False, indent=2))

    # 可选：落盘 JSON（CI 直接读这个文件，避免解析 stdout）
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  📁 Report saved to {out_path}")

    if new_candidates:
        print(f"\n✅ {len(new_candidates)} new candidates found. Review and add to platforms.json.")
        sys.exit(1)
    else:
        print("\n✅ No new candidates found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
