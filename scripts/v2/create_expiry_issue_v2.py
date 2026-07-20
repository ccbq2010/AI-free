#!/usr/bin/env python3
"""v2 过期检测 Issue（读 data/expiry_report_v2.json）。

与 v1 的 `create_issue.py --mode expiry` 等效，但数据源是 v2 报告。
无问题时自动跳过，CI 可无脑 always 运行。
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
REPORT_FILE = ROOT / "data" / "expiry_report_v2.json"


def _clean(text: object) -> str:
    if text is None:
        text = ""
    return str(text).replace("\n", " ").replace("\r", " ").strip().replace("|", "/")


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


def build_body(report: dict) -> str:
    parts: list[str] = ["## ⚠️ v2 过期检测报告\n"]
    parts.append(f"扫描日期: {report.get('scan_date', 'N/A')}")
    parts.append(f"平台总数: {report.get('total_platforms', 'N/A')}")
    parts.append(f"发现问题: {report.get('issues_found', 0)}\n")
    parts.append("| 平台 | 问题类型 | 详情 |")
    parts.append("|------|----------|------|")
    for issue in report.get("issues", []):
        parts.append(
            f"| {_clean(issue.get('name') or issue.get('id'))} "
            f"| {_clean(issue.get('issue'))} "
            f"| {_clean(issue.get('detail'))} |"
        )
    parts.append("\n### 操作说明")
    parts.append("- 确认过期: 修改 `data/platforms-v2.json` 中该平台 `status` 为 `expired`")
    parts.append("- 链接失效: 更新 `url` 字段或标记 `expired`")
    parts.append("- 误报: 直接关闭 Issue")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="v2 过期检测建 Issue")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        print("[INFO] 无 v2 过期报告，跳过。")
        return

    if not report.get("issues_found"):
        print("[INFO] v2 过期检测未发现问题，跳过 Issue。")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = f"⚠️ v2 平台过期/链接失效检测 ({today})"
    body = build_body(report)

    if args.dry_run:
        print("DRY RUN")
        print(f"title: {title}")
        print(body)
        return

    token = os.environ.get("GITHUB_TOKEN")
    repo = _repo_full_name()
    if not token or not repo:
        print("[ERROR] 缺少 GITHUB_TOKEN 或无法确定仓库。", file=sys.stderr)
        sys.exit(2)

    payload = json.dumps({
        "title": title, "body": body, "labels": ["bot", "maintenance", "v2"],
    }).encode("utf-8")
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


if __name__ == "__main__":
    main()
