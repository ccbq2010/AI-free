#!/usr/bin/env python3
"""v2 高置信度候选 → 自动 PR。

读取 LLM 抽取结果中的 high_confidence 条目：
  1. 转成 platforms.json 格式，追加到 data/platforms-v2.json
  2. 创建 git 分支、commit、push
  3. 调 GitHub API 开 PR（人工点 Merge 即上线）

幂等：按 URL 域名 + 归一化名称去重，已存在于 platforms-v2.json /
platforms.json 或已有同名 open PR 时跳过。

用法：
  python scripts/v2/auto_pr_v2.py < extracted_v2.json
  python scripts/v2/auto_pr_v2.py --dry-run < extracted_v2.json

环境变量：
  GITHUB_TOKEN       必填（Actions 注入；需 contents:write + pull-requests:write）
  GITHUB_REPOSITORY  owner/repo（Actions 自动注入）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
DATA_V2 = ROOT / "data" / "platforms-v2.json"
DATA_V1 = ROOT / "data" / "platforms.json"

MAX_PR_ITEMS = 5  # 单次 PR 最多包含的条目数，防失控


# ── 工具 ────────────────────────────────────────────────

def slugify(name: str) -> str:
    """从平台名生成 id slug。"""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:40] or "unknown"


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower() if url else ""


def _load_platforms(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def _repo_full_name() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo
    try:
        url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(ROOT), stderr=subprocess.DEVNULL, text=True,
        ).strip()
        if url.startswith("git@"):
            return url.split(":", 1)[1].removesuffix(".git")
        parts = url.rsplit("/", 2)
        return parts[-2].removesuffix(".git") + "/" + parts[-1].removesuffix(".git")
    except Exception:  # noqa: BLE001
        return ""


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(ROOT), check=check,
        capture_output=True, text=True,
    )


def _github_api(method: str, path: str, payload: dict | None = None) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = _repo_full_name()
    url = f"https://api.github.com/repos/{repo}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── 候选 → platform 条目 ────────────────────────────────

def to_platform_entry(item: dict) -> dict:
    """把 LLM 抽取结果转成 platforms.json 格式。"""
    name = (item.get("name") or item.get("_original_name") or "unknown").strip()
    url = item.get("url") or item.get("_original_url") or ""
    benefit = (item.get("benefit") or "").strip()
    # benefit_highlight：取 benefit 中含数字/关键词的短片段
    highlights = re.findall(r"[\w.+$¥￥]*\d+[\w.+$¥￥]*\s*(?:积分|tokens?|credits?|额度|代金券|元|\$|calls?)?",
                            benefit)[:4]
    entry = {
        "id": slugify(name),
        "name": name,
        "tier": "hidden_gem",
        "provider": (item.get("provider") or "").strip(),
        "benefit": benefit,
        "benefit_highlight": [h.strip() for h in highlights if h.strip()],
        "url": url,
        "tags": item.get("tags") or [],
        "deadline": item.get("deadline") or None,
        "referral": {"type": "none"},
        "status": "active",
        "note": f"v2 自动收录 ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})，"
                f"来源 {item.get('_source', '?')}，confidence={item.get('confidence', '?')}。"
                "请人工核对后 Merge。",
    }
    return entry


def filter_duplicates(items: list[dict]) -> list[dict]:
    """剔除已在 v1/v2 数据中的候选（按域名 + slug）。"""
    existing_ids: set[str] = set()
    existing_domains: set[str] = set()
    for path in (DATA_V2, DATA_V1):
        for p in _load_platforms(path):
            existing_ids.add(p.get("id", ""))
            d = _domain(p.get("url", ""))
            if d:
                existing_domains.add(d)

    out: list[dict] = []
    seen_batch: set[str] = set()
    for item in items:
        entry = to_platform_entry(item)
        d = _domain(entry["url"])
        if entry["id"] in existing_ids or entry["id"] in seen_batch:
            continue
        if d and d in existing_domains:
            continue
        seen_batch.add(entry["id"])
        out.append(entry)
    return out


# ── PR 流程 ─────────────────────────────────────────────

def has_open_pr(branch: str) -> bool:
    """检查是否已有同分支的 open PR，避免重复开。"""
    try:
        repo = _repo_full_name()
        prs = _github_api("GET", f"/pulls?state=open&head={repo.split('/')[0]}:{branch}")
        return len(prs) > 0
    except Exception as e:  # noqa: BLE001
        print(f"  [WARN] 查询 open PR 失败: {e}", file=sys.stderr)
        return False


def create_pr(entries: list[dict], dry_run: bool = False) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    branch = f"bot/v2-auto-{today.replace('-', '')}"
    title = f"🤖 v2 自动收录 {len(entries)} 个新用户福利平台 ({today})"

    body_lines = [
        "## v2 高置信度自动收录\n",
        "以下候选经 LLM 判定 `has_new_user_benefit=true` 且 `confidence >= 0.8`，",
        "已按 platforms.json 格式追加到 `data/platforms-v2.json`。\n",
        "**请人工核对福利描述与链接后 Merge。**\n",
        "| 平台 | 福利 | 置信度 | 链接 |",
        "|------|------|--------|------|",
    ]
    # 附带原始置信度信息
    for e in entries:
        benefit = e["benefit"].replace("|", "/")[:60]
        link = f"[链接]({e['url']})" if e["url"] else ""
        conf = e.get("note", "")
        m = re.search(r"confidence=([\d.]+)", conf)
        conf_s = m.group(1) if m else "?"
        body_lines.append(f"| {e['name']} | {benefit} | {conf_s} | {link} |")
    body_lines.append("\n---")
    body_lines.append("*由 check-sources-v2.yml 自动生成*")
    body = "\n".join(body_lines)

    if dry_run:
        print("=" * 60)
        print("DRY RUN — 不会真正建分支/PR")
        print(f"branch: {branch}")
        print(f"title:  {title}")
        print("---- body ----")
        print(body)
        print("---- entries ----")
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return

    if has_open_pr(branch):
        print(f"[INFO] 已存在 {branch} 的 open PR，跳过。")
        return

    # 1) 更新数据文件
    platforms = _load_platforms(DATA_V2)
    platforms.extend(entries)
    DATA_V2.write_text(
        json.dumps(platforms, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # 2) git 分支 + commit + push
    _git("checkout", "-b", branch)
    _git("add", str(DATA_V2.relative_to(ROOT)))
    _git("-c", "user.name=github-actions[bot]",
         "-c", "user.email=github-actions[bot]@users.noreply.github.com",
         "commit", "-m", f"feat(v2): auto-add {len(entries)} platforms ({today})")
    _git("push", "-u", "origin", branch)

    # 3) 开 PR
    pr = _github_api("POST", "/pulls", {
        "title": title,
        "body": body,
        "head": branch,
        "base": "main",
    })
    print(f"[OK] PR 已创建: {pr.get('html_url', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(description="v2 高置信度候选自动 PR")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    extracted = json.loads(sys.stdin.read())
    high = extracted.get("high_confidence", []) if isinstance(extracted, dict) else []
    if not high:
        print("[INFO] 无高置信度候选，跳过 PR。")
        return

    print(f"High-confidence candidates: {len(high)}")
    entries = filter_duplicates(high)
    if not entries:
        print("[INFO] 全部候选均为已收录/重复，跳过 PR。")
        return

    entries = entries[:MAX_PR_ITEMS]
    print(f"After dedup, {len(entries)} entries to PR (cap {MAX_PR_ITEMS}).")
    try:
        create_pr(entries, dry_run=args.dry_run)
    except urllib.error.HTTPError as e:
        print(f"[ERROR] GitHub API {e.code}: {e.read().decode('utf-8', errors='replace')}",
              file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] git 失败: {e.stderr}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
