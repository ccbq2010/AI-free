#!/usr/bin/env python3
"""官方活动页 diff 监控（v2 新增）—— 抓「老产品改福利政策」。

社交巡检只能发现新平台发布；老平台调整活动（如 ZCode 从 500 万/天
涨到 800 万/天、智谱礼包从 2000 万变 2500 万）没有任何渠道会主动
报告。本脚本定期抓取官方活动/定价页，做归一化文本 diff：
  - 首次运行：记录基线快照，不告警
  - 内容变化：更新快照 + 创建 Issue（配置了 GITHUB_TOKEN 时）

快照：data/promo_snapshots.json（提交进仓库持久化，workflow 负责 commit）
退出码：0 = 无变化/建基线；1 = 有变化；2 = 运行错误
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from selectolax.parser import HTMLParser

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR.parent))  # scripts/ 可导入

from v2.http_util import fetch_text  # noqa: E402

SNAPSHOT_FILE = ROOT / "data" / "promo_snapshots.json"

# 官方活动/定价页清单——JS 空壳页产出稳定文本，不会误报
PROMO_PAGES = [
    {"name": "智谱上新活动", "url": "https://docs.bigmodel.cn/cn/update/promotion"},
    {"name": "ZCode changelog", "url": "https://zcode.z.ai/changelog"},
    {"name": "硅基流动动态", "url": "https://www.siliconflow.cn/news"},
    {"name": "CodeBuddy 邀请活动", "url": "https://www.codebuddy.cn/events/invite"},
    {"name": "TRAE 定价", "url": "https://www.trae.cn/pricing"},
    {"name": "Kiro 定价", "url": "https://kiro.dev/pricing/"},
]

_WS_RE = re.compile(r"\s+")


def _extract_text(html: str) -> str:
    tree = HTMLParser(html)
    for tag in tree.css("script, style, noscript, svg"):
        tag.decompose()
    return _WS_RE.sub(" ", tree.body.text(separator=" ", strip=True) if tree.body else "").strip()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_snapshots() -> dict:
    if SNAPSHOT_FILE.exists():
        try:
            return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print("[WARN] 快照文件损坏，重建基线", file=sys.stderr)
    return {}


def _github_api(method: str, path: str, payload: dict | None = None) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        return {}
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}{path}",
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _create_issue(page: dict, old: dict, new_hash: str, new_excerpt: str) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    title = f"📢 官方活动页变更：{page['name']}（{today}）"
    body = (
        f"官方页面内容与上次快照不一致，可能存在福利政策调整，请人工核对。\n\n"
        f"- **页面**: [{page['name']}]({page['url']})\n"
        f"- **旧快照**: {old.get('hash', '?')[:12]} @ {old.get('updated', '?')}\n"
        f"- **新快照**: {new_hash[:12]}\n\n"
        f"<details><summary>旧内容摘录</summary>\n\n{old.get('excerpt', '')[:400]}\n\n</details>\n"
        f"<details><summary>新内容摘录</summary>\n\n{new_excerpt[:400]}\n\n</details>\n\n"
        f"*由 check_promo_pages.py 自动创建*"
    )
    try:
        issue = _github_api("POST", "/issues", {"title": title, "body": body})
        print(f"  [OK] Issue 已创建: {issue.get('html_url', '')}")
    except urllib.error.HTTPError as e:
        print(f"  [WARN] Issue 创建失败 {e.code}（本地运行属正常）", file=sys.stderr)


def main() -> None:
    snapshots = _load_snapshots()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    changed: list[tuple[dict, dict, str, str]] = []
    errors = 0

    for page in PROMO_PAGES:
        name, url = page["name"], page["url"]
        html = fetch_text(url)
        if html is None:
            print(f"  [ERROR] {name} fetch failed")
            errors += 1
            continue
        text = _extract_text(html)
        if len(text) < 50:
            print(f"  [WARN] {name} 正文过短（可能 JS 渲染），跳过本轮")
            continue
        h = _sha(text)
        old = snapshots.get(url)

        if old is None:
            snapshots[url] = {"hash": h, "updated": today, "excerpt": text[:400]}
            print(f"  [BASELINE] {name} 首次记录快照 {h[:12]}")
        elif old.get("hash") != h:
            print(f"  [CHANGED] {name}: {old.get('hash', '?')[:12]} -> {h[:12]}")
            changed.append((page, old, h, text))
            snapshots[url] = {"hash": h, "updated": today, "excerpt": text[:400]}
        else:
            print(f"  [OK] {name} 无变化")

    SNAPSHOT_FILE.write_text(
        json.dumps(snapshots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for page, old, new_hash, new_excerpt in changed:
        _create_issue(page, old, new_hash, new_excerpt)

    if errors and not changed:
        sys.exit(2)
    if changed:
        print(f"\n{len(changed)} 个官方页面有变更。")
        sys.exit(1)
    print("\n所有官方页面无变化。")
    sys.exit(0)


if __name__ == "__main__":
    main()
