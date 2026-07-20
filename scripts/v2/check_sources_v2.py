#!/usr/bin/env python3
"""v2 多源免费 AI 新用户福利巡检脚本。

与 v1（scripts/check_sources.py）并行，互不影响：
  - 数据源：v1 六源 + v2 新增三源（官网活动页 / 中文社区 / 新品监控）
  - 过滤：v2 精准白名单 + 反过滤黑名单（比 v1 严格）
  - 数据：对 data/platforms-v2.json 与 data/platforms.json 双去重
  - 输出：data/last_scan_v2.json

退出码：0 = 无新候选；1 = 发现新候选；2 = 运行错误。
"""

from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR.parent))  # scripts/ 可导入（v1 fetchers）
sys.path.insert(0, str(ROOT))

from v2 import RawCandidate, is_new_user_benefit_candidate  # noqa: E402

DATA_V2 = ROOT / "data" / "platforms-v2.json"
DATA_V1 = ROOT / "data" / "platforms.json"
BLACKLIST_FILE = ROOT / "data" / "review_blacklist.json"

_MD_LINK_RE = re.compile(r"\[(.+?)\]\(.+?\)")


def _strip_md_link(text: str) -> str:
    return _MD_LINK_RE.sub(r"\1", text)


def normalize_name(name: str) -> str:
    name = _strip_md_link(name)
    return re.sub(r"[^a-z0-9一-鿿]", "", name.lower())


# ── 已收录平台（v1 + v2 双去重） ─────────────────────────

def _load_platforms(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def known_ids_and_domains() -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    domains: set[str] = set()
    for path in (DATA_V2, DATA_V1):
        for p in _load_platforms(path):
            if p.get("id"):
                ids.add(normalize_name(p["id"]))
            if p.get("name"):
                ids.add(normalize_name(p["name"]))
            url = p.get("url", "")
            if url:
                domains.add(urlparse(url).netloc.lower())
    return ids, domains


def get_blacklist() -> dict:
    if BLACKLIST_FILE.exists():
        try:
            return json.loads(BLACKLIST_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"domains": [], "names": []}


# ── 多源抓取调度 ────────────────────────────────────────

# v1 六源（复用现有 fetchers，结果再用 v2 白名单过滤）
V1_FETCHERS = [
    ("GitHub",      "fetchers.github_repos",  "fetch_all"),
    ("HackerNews",  "fetchers.hackernews",    "fetch_all"),
    ("OpenRouter",  "fetchers.openrouter",    "fetch_all"),
    ("RSS",         "fetchers.rss_feeds",     "fetch_all"),
    ("ChineseNews", "fetchers.chinese_news",  "fetch_all"),
    ("GHTopics",    "fetchers.github_topics", "fetch_all"),
]

# v2 三源
V2_FETCHERS = [
    ("OfficialSites", "v2.fetchers.official_sites", "fetch_all"),
    ("Community",     "v2.fetchers.community",      "fetch_all"),
    ("NewProducts",   "v2.fetchers.new_products",   "fetch_all"),
]


def _run_fetcher(name: str, module_path: str, func_name: str) -> list[RawCandidate]:
    mod = importlib.import_module(module_path)
    func = getattr(mod, func_name)
    return list(func())


def fetch_all_sources() -> list[RawCandidate]:
    all_candidates: list[RawCandidate] = []
    per_source: list[tuple[str, int, str]] = []

    # v1 源：抓到的是 v1 RawCandidate，字段一致可直接用，但需过 v2 白名单
    for name, module_path, func_name in V1_FETCHERS:
        try:
            raw = _run_fetcher(name, module_path, func_name)
            filtered = []
            for c in raw:
                text = f"{c.name} {c.benefit} {c.raw}"
                ok, white, _ = is_new_user_benefit_candidate(text)
                if ok:
                    c.keywords = sorted(set(c.keywords) | set(white))
                    filtered.append(RawCandidate(
                        source=c.source, name=c.name, benefit=c.benefit,
                        raw=c.raw, url=c.url, keywords=c.keywords,
                    ))
            all_candidates.extend(filtered)
            status = "WARN:0" if not filtered else "OK"
            per_source.append((name, len(filtered), status))
        except Exception as e:  # noqa: BLE001
            per_source.append((name, 0, f"ERROR:{e}"))
            print(f"  [ERROR] {name} fetcher failed: {e}", file=sys.stderr)

    # v2 源：fetcher 内部已做白名单过滤
    for name, module_path, func_name in V2_FETCHERS:
        try:
            result = _run_fetcher(name, module_path, func_name)
            all_candidates.extend(result)
            status = "WARN:0" if not result else "OK"
            per_source.append((name, len(result), status))
        except Exception as e:  # noqa: BLE001
            per_source.append((name, 0, f"ERROR:{e}"))
            print(f"  [ERROR] {name} fetcher failed: {e}", file=sys.stderr)

    print("\n  ── Source Summary (v2) ──")
    for name, count, status in per_source:
        flag = "!" if ("WARN" in status or "ERROR" in status) else " "
        print(f"    [{flag}] {name:<15s} {count:>3} candidates  [{status}]")
    print(f"    {'':>18}{sum(c for _, c, _ in per_source):>3} total\n")

    return all_candidates


# ── 去重与过滤 ──────────────────────────────────────────

def deduplicate(candidates: list[RawCandidate]) -> list[RawCandidate]:
    seen_domains: set[str] = set()
    seen_names: set[str] = set()
    unique: list[RawCandidate] = []

    for c in candidates:
        c.name = _strip_md_link(c.name)
        domain = urlparse(c.url).netloc.lower() if c.url else ""
        if domain and domain in seen_domains:
            continue
        norm = normalize_name(c.name)
        if norm and norm in seen_names:
            continue
        if domain:
            seen_domains.add(domain)
        if norm:
            seen_names.add(norm)
        unique.append(c)
    return unique


def filter_known(candidates: list[RawCandidate]) -> list[RawCandidate]:
    known_ids, known_domains = known_ids_and_domains()
    blacklist = get_blacklist()
    black_domains = {d.lower() for d in blacklist.get("domains", [])}
    black_names = {normalize_name(n) for n in blacklist.get("names", [])}

    new: list[RawCandidate] = []
    for c in candidates:
        norm = normalize_name(c.name)
        domain = urlparse(c.url).netloc.lower() if c.url else ""
        if norm and norm in known_ids:
            continue
        if domain and domain in known_domains:
            continue
        if domain in black_domains or norm in black_names:
            continue
        new.append(c)
    return new


# ── 报告 ────────────────────────────────────────────────

def candidate_to_dict(c: RawCandidate) -> dict:
    return {
        "source": c.source,
        "name": c.name,
        "benefit": c.benefit,
        "raw": c.raw,
        "url": c.url,
        "keywords": c.keywords,
    }


def generate_report(candidates: list[RawCandidate], known_count: int) -> dict:
    return {
        "version": "v2",
        "known_platforms_count": known_count,
        "candidates_total": len(candidates),
        "new_candidates": [candidate_to_dict(c) for c in candidates[:80]],
        "sources_scanned": len(V1_FETCHERS) + len(V2_FETCHERS),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AI-free multi-source scanner v2")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Save JSON report to file")
    args = parser.parse_args()

    print("=" * 60)
    print("AI-free multi-source scanner  v2.0 (new-user-benefit focused)")
    print("=" * 60)

    known_ids, _ = known_ids_and_domains()

    print("\n[Phase 1] Fetching from all sources (v1 x6 + v2 x3)...")
    candidates = fetch_all_sources()
    print(f"  Total raw candidates (post-whitelist): {len(candidates)}")

    print("\n[Phase 2] Deduplicating...")
    candidates = deduplicate(candidates)
    print(f"  After dedup: {len(candidates)}")

    print("\n[Phase 3] Filtering known platforms (v1+v2)...")
    new_candidates = filter_known(candidates)
    print(f"  New candidates: {len(new_candidates)}")

    report = generate_report(new_candidates, known_count=len(known_ids))
    print("\n" + json.dumps(report, ensure_ascii=False, indent=2))

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        print(f"\n  Report saved to {out_path}")

    if new_candidates:
        print(f"\n{len(new_candidates)} new candidates found.")
        sys.exit(1)
    print("\nNo new candidates found.")
    sys.exit(0)


if __name__ == "__main__":
    main()
