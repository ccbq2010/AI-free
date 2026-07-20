#!/usr/bin/env python3
"""v2 低置信度候选 → 建 Issue 人工审核。

读取 LLM 抽取结果中的 low_confidence 条目（0.5 <= confidence < 0.8
且 has_new_user_benefit=true），建 Issue 等待人工处理。
沿用 v1 create_issue.py 的纯 Python + urllib 风格，不依赖 github-script。

用法：
  python scripts/v2/create_issue_v2.py < extracted_v2.json
  python scripts/v2/create_issue_v2.py --dry-run < extracted_v2.json

环境变量：
  GITHUB_TOKEN / GITHUB_REPOSITORY（Actions 自动注入）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent

MAX_ISSUE_ITEMS = 15


def _clean(text: object, limit: int | None = None) -> str:
    if text is None:
        text = ""
    text = str(text).replace("\n", " ").replace("\r", " ").strip().replace("|", "/")
    return text[:limit] if limit else text


def _repo_full_name() -> str:
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo
    import subprocess
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


def build_body(low: list[dict]) -> str:
    parts: list[str] = [
        "## 🤖 v2 巡检发现待审核候选（低置信度）\n",
        "以下候选经 LLM 判定可能有新用户福利，但置信度在 0.5–0.8 之间，",
        "需要人工确认后手动加入 `data/platforms-v2.json`。\n",
        "| 名称 | 福利 | 置信度 | 来源 | 链接 |",
        "|------|------|--------|------|------|",
    ]
    for item in low[:MAX_ISSUE_ITEMS]:
        name = _clean(item.get("name") or item.get("_original_name") or "?")
        benefit = _clean(item.get("benefit"), limit=60)
        try:
            conf = f"{float(item.get('confidence') or 0):.2f}"
        except (TypeError, ValueError):
            conf = "0.00"
        source = _clean(item.get("_source"))
        url = item.get("url") or item.get("_original_url") or ""
        link = f"[链接]({url})" if url else ""
        parts.append(f"| {name} | {benefit} | {conf} | {source} | {link} |")
    parts.append("\n### 操作说明")
    parts.append("- 确认收录：按 platforms.json 格式手动添加到 `data/platforms-v2.json`")
    parts.append("- 拒绝：将域名/名称加入 `data/review_blacklist.json`")
    parts.append("- 高置信度候选已另开自动 PR，不在本 Issue 内")
    return "\n".join(parts) + "\n"


def create_issue(title: str, body: str, labels: list[str], dry_run: bool = False) -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repo = _repo_full_name()

    if dry_run:
        print("=" * 60)
        print("DRY RUN — 不会真正创建 Issue")
        print(f"repo:   {repo or '(unknown)'}")
        print(f"title:  {title}")
        print(f"labels: {labels}")
        print("---- body ----")
        print(body)
        return

    if not token or not repo:
        print("[ERROR] 缺少 GITHUB_TOKEN 或无法确定仓库。", file=sys.stderr)
        sys.exit(2)

    payload = json.dumps({"title": title, "body": body, "labels": labels}).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=payload, method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            print(f"[OK] Issue 已创建: {result.get('html_url', '')}")
    except urllib.error.HTTPError as e:
        print(f"[ERROR] GitHub API {e.code}: {e.read().decode('utf-8', errors='replace')}",
              file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="v2 低置信度候选建 Issue")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    extracted = json.loads(sys.stdin.read())
    low = extracted.get("low_confidence", []) if isinstance(extracted, dict) else []
    if not low:
        print("[INFO] 无低置信度候选，跳过 Issue。")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    create_issue(
        title=f"🤖 v2 待审核：{len(low)} 个候选平台 ({today})",
        body=build_body(low),
        labels=["bot", "content-update", "v2-review"],
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
