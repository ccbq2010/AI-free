#!/usr/bin/env python3
"""在 CI 中创建 GitHub Issue（替代脆弱的 inline actions/github-script JS）。

背景：check-sources.yml / check-expiry.yml 原本用 actions/github-script@v7
执行内联 JavaScript 来建 Issue。GitHub Actions 把该 action 从 Node 20
强制升级到 Node 24 后，内联脚本求值时抛出
``SyntaxError: Unexpected token '**'``，导致 "Check New Sources" 每次失败。
本脚本用 Python 完成同样工作，避免 Node/github-script 的运行时脆弱性，
且与仓库其余脚本（全 Python）保持一致。

用法：
  python scripts/create_issue.py --mode new-sources   # 发现新候选平台
  python scripts/create_issue.py --mode expiry        # 过期/链接失效
  python scripts/create_issue.py --mode new-sources --dry-run   # 只打印不提交

读取：
  /tmp/extracted.json        LLM 抽取结果（可选，new-sources 模式优先用）
  data/last_scan.json        原始巡检报告（new-sources 回退用）
  data/expiry_report.json    过期检测报告（expiry 模式用）

环境变量（GitHub Actions 自动注入）：
  GITHUB_TOKEN          必填，用于调用 Issues API
  GITHUB_REPOSITORY     自动注入为 "owner/repo"；本地缺失时从 git remote 推断
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ── 工具函数 ─────────────────────────────────────────────

def _read_json(path: Path, default=None):
    """安全读取 JSON 文件，失败返回 default。"""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _clean(text, limit: int | None = None) -> str:
    """清洗单元格文本：去换行、转义竖线、可选截断。"""
    if text is None:
        text = ""
    text = str(text).replace("\n", " ").replace("\r", " ").strip()
    text = text.replace("|", "/")  # 避免 markdown 表格竖线冲突
    if limit:
        text = text[:limit]
    return text


def _repo_full_name() -> str:
    """返回 "owner/repo"。优先用 GITHUB_REPOSITORY，否则从 git remote 推断。"""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return repo
    # 本地回退：解析 git remote
    import subprocess
    try:
        url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            cwd=str(ROOT), stderr=subprocess.DEVNULL, text=True,
        ).strip()
        # https://github.com/owner/repo.git  or  git@github.com:owner/repo.git
        if url.startswith("git@"):
            return url.split(":", 1)[1].removesuffix(".git")
        return url.rsplit("/", 2)[-2].removesuffix(".git") + "/" + url.rsplit("/", 1)[-1].removesuffix(".git")
    except Exception:
        return ""


# ── Issue 正文构建 ───────────────────────────────────────

def build_new_sources_body() -> str:
    """构建「发现新候选平台」Issue 正文（对应原 check-sources.yml 的 JS）。"""
    parts: list[str] = ["## 🤖 自动巡检发现新候选平台\n"]

    # 1) 优先使用 LLM 抽取结果
    extracted = _read_json(Path("/tmp/extracted.json"))
    if isinstance(extracted, list) and len(extracted) > 0:
        parts.append("### LLM 结构化抽取结果\n")
        parts.append("| 名称 | 福利 | 置信度 | 链接 |")
        parts.append("|------|------|--------|------|")
        for item in extracted[:20]:  # 修复：原 JS 写成 slice(20)，应为 slice(0,20)
            name = _clean(item.get("name") or "?")
            benefit = _clean(item.get("benefit"), limit=60)
            conf = (item.get("confidence") or 0)
            try:
                conf = f"{float(conf):.2f}"
            except (TypeError, ValueError):
                conf = "0.00"
            url = item.get("url") or item.get("_original_url") or ""
            link = f"[链接]({url})" if url else ""
            parts.append(f"| {name} | {benefit} | {conf} | {link} |")
        parts.append("")
    else:
        # 2) 回退到原始巡检报告
        report = _read_json(ROOT / "data" / "last_scan.json", default={})
        cands = report.get("new_candidates", []) if isinstance(report, dict) else []
        if cands:
            parts.append("### 原始候选（LLM 抽取失败）\n")
            for c in cands[:15]:
                name = _clean(c.get("name"))
                benefit = _clean(c.get("benefit"), limit=80)
                source = _clean(c.get("source"))
                parts.append(f"- **{name}** — {benefit} ({source})")
            parts.append("")
        else:
            parts.append("_本次未发现新候选，或抽取/解析均失败，请手动检查 CI 日志。_\n")

    # 3) 过期检查摘要（如果有问题）
    expiry = _read_json(ROOT / "data" / "expiry_report.json", default={})
    if isinstance(expiry, dict):
        issues = expiry.get("issues", []) or []
        if issues:
            parts.append("\n### ⚠️ 过期/异常检查\n")
            for issue in issues[:10]:  # 修复：原 JS 写成 slice(10)，应为 slice(0,10)
                name = _clean(issue.get("name") or issue.get("id"))
                itype = _clean(issue.get("issue"))
                detail = _clean(issue.get("detail"))
                parts.append(f"- **{name}**: {itype} ({detail})")
            parts.append("")

    parts.append("\n### 操作说明")
    parts.append("- 回复 `/accept <平台名>` 添加到 platforms.json")
    parts.append("- 回复 `/reject <平台名>` 加入黑名单")
    parts.append("- 30 天无响应自动关闭")
    return "\n".join(parts) + "\n"


def build_expiry_body() -> str:
    """构建「过期/链接失效」Issue 正文（对应原 check-expiry.yml 的 JS）。"""
    report = _read_json(ROOT / "data" / "expiry_report.json", default={})
    if not isinstance(report, dict):
        report = {}

    scan_date = report.get("scan_date", "N/A")
    total = report.get("total_platforms", "N/A")
    found = report.get("issues_found", 0)
    issues = report.get("issues", []) or []

    parts: list[str] = ["## ⚠️ 过期检测报告\n"]
    parts.append(f"扫描日期: {scan_date}")
    parts.append(f"平台总数: {total}")
    parts.append(f"发现问题: {found}\n")

    parts.append("| 平台 | 问题类型 | 详情 |")
    parts.append("|------|----------|------|")
    for issue in issues:
        name = _clean(issue.get("name") or issue.get("id"))
        itype = _clean(issue.get("issue"))
        detail = _clean(issue.get("detail"))
        parts.append(f"| {name} | {itype} | {detail} |")

    parts.append("\n### 操作说明")
    parts.append("- 确认过期: 修改 `data/platforms.json` 中该平台 `status` 为 `expired`")
    parts.append("- 链接失效: 更新 `url` 字段或标记 `expired`")
    parts.append("- 误报: 回复 `/ignore` 关闭 Issue")
    return "\n".join(parts) + "\n"


# ── GitHub API ──────────────────────────────────────────

def create_issue(title: str, body: str, labels: list[str], dry_run: bool = False) -> dict:
    """通过 GitHub REST API 创建 Issue。"""
    token = os.environ.get("GITHUB_TOKEN")
    repo = _repo_full_name()

    if dry_run:
        print("=" * 60)
        print("DRY RUN — 不会真正创建 Issue")
        print("=" * 60)
        print(f"repo:   {repo or '(unknown)'}")
        print(f"title:  {title}")
        print(f"labels: {labels}")
        print("---- body ----")
        print(body)
        print("---- end body ----")
        return {"dry_run": True, "title": title}

    if not token:
        print("[ERROR] 缺少 GITHUB_TOKEN 环境变量，无法创建 Issue。", file=sys.stderr)
        sys.exit(2)
    if not repo:
        print("[ERROR] 无法确定仓库（GITHUB_REPOSITORY 未设置且 git remote 解析失败）。", file=sys.stderr)
        sys.exit(2)

    url = f"https://api.github.com/repos/{repo}/issues"
    payload = json.dumps({"title": title, "body": body, "labels": labels}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        method="POST",
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
            print(f"[OK] Issue 已创建: {result.get('html_url', url)}")
            return result
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        print(f"[ERROR] GitHub API 返回 {e.code}: {body_text}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"[ERROR] 网络错误: {e}", file=sys.stderr)
        sys.exit(1)


# ── 入口 ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="从 CI 扫描结果创建 GitHub Issue")
    parser.add_argument("--mode", required=True, choices=["new-sources", "expiry"],
                        help="Issue 类型")
    parser.add_argument("--dry-run", action="store_true", help="只打印不创建 Issue")
    args = parser.parse_args()

    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if args.mode == "new-sources":
        title = f"🤖 发现新的免费 AI 资源 ({today})"
        body = build_new_sources_body()
        labels = ["bot", "content-update"]
    else:
        # expiry 模式：无问题则跳过（workflow 可无脑 always 运行本脚本）
        report = _read_json(ROOT / "data" / "expiry_report.json", default={})
        issues_found = (report or {}).get("issues_found", 0) if isinstance(report, dict) else 0
        if not issues_found:
            print("[INFO] 过期检测未发现问题，跳过 Issue 创建。")
            return
        title = f"⚠️ 平台过期/链接失效检测 ({today})"
        body = build_expiry_body()
        labels = ["bot", "maintenance"]

    create_issue(title, body, labels, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
