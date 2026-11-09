#!/usr/bin/env python3
"""v2 过期检测 —— 数据源指向 data/platforms-v2.json。

复用 v1 check_expiry.py 的全部检测逻辑（deadline / URL 状态 /
页面过期标记 / 推荐码一致性），仅替换输入与报告输出路径。
每日随 check-sources-v2.yml 一起运行。

输出：data/expiry_report_v2.json
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
DATA_FILE = ROOT / "data" / "platforms-v2.json"
REPORT_FILE = ROOT / "data" / "expiry_report_v2.json"

# 动态加载 v1 check_expiry.py 为模块，复用其检测函数
_spec = importlib.util.spec_from_file_location(
    "check_expiry_v1", ROOT / "scripts" / "check_expiry.py")
_v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_v1)  # type: ignore[union-attr]


# ── deadline 判定 ────────────────────────────────────────────
# 2026-11-09 起数据侧新增两个机器字段（详见 data/platforms-v2.json）：
#   deadline_iso   绝对截止日（YYYY-MM-DD 或 null）
#   deadline_kind  date / rolling / long_term / unknown
# 旧实现只认 deadline 自由文本开头的 ISO 日期，22 条里 21 条形如「长期（…）」
# 直接跳过 —— 等于过期检测对全库基本失明（2026-10-23 实测 0/22 覆盖）。
# 现在优先读 deadline_iso；没有该字段的老条目回退到旧的文本前缀解析。
_ISO_PREFIX = re.compile(r"^\s*(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})")

# verified_at 超过这么久没复核 → 进 stale 报告（不建 Issue、不染红，只出 warning）
STALE_DAYS = 45


def _resolve_deadline(platform: dict) -> date | None:
    """取该条目的绝对截止日；没有则 None。"""
    iso = platform.get("deadline_iso")
    if iso:
        try:
            return date.fromisoformat(str(iso)[:10])
        except ValueError:
            return None
    m = _ISO_PREFIX.match(str(platform.get("deadline") or ""))
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _check_deadline_v2(platform: dict) -> str | None:
    """与 v1 同名同契约，但读机器字段，并能区分长期/滚动型。

    rolling（活动型/按开通日滚动）与 long_term（政策型长期）没有绝对日期，
    不做日期判定，改由 verified_at 陈旧度兜底。
    """
    kind = platform.get("deadline_kind") or "unknown"
    if kind in ("long_term", "rolling") and not platform.get("deadline_iso"):
        return None
    d = _resolve_deadline(platform)
    if d is None:
        return None
    if d < date.today():
        return f"deadline {platform.get('deadline') or d.isoformat()} passed"
    return None


def _stale_entries(data: list[dict]) -> list[dict]:
    """active 条目里 verified_at 缺失或过旧的清单（只报告，不建 Issue）。"""
    today = date.today()
    stale: list[dict] = []
    for p in data:
        if p.get("status") != "active":
            continue
        v = p.get("verified_at")
        if not v:
            stale.append({"id": p.get("id"), "name": p.get("name"), "reason": "无 verified_at"})
            continue
        try:
            d = date.fromisoformat(str(v)[:10])
        except ValueError:
            stale.append({"id": p.get("id"), "name": p.get("name"),
                          "reason": f"verified_at 格式异常: {v}"})
            continue
        days = (today - d).days
        if days > STALE_DAYS:
            stale.append({"id": p.get("id"), "name": p.get("name"),
                          "reason": f"verified_at {v}（{days} 天前）"})
    return stale


_v1.check_deadline = _check_deadline_v2


def main() -> None:
    print("=" * 50)
    print("AI-free expiry scanner (v2)")
    print("=" * 50)

    if not DATA_FILE.exists():
        print(f"[INFO] {DATA_FILE} 不存在，跳过。")
        REPORT_FILE.write_text(json.dumps({
            "version": "v2",
            "scan_date": date.today().isoformat(),
            "total_platforms": 0,
            "issues_found": 0,
            "issues": [],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    # 把 v1 模块的数据文件指向 v2，然后复用 scan_all
    _v1.DATA_FILE = DATA_FILE
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    issues = _v1.scan_all()

    # 已下架（status != active）的条目不做 URL/内容告警：它们的链接失效是预期结果
    # 而不是待办。2026-11-09 之前 Dyad（已 expired）的 GitHub 页面偶发 504，
    # 每次关单后次日又开一张新单 —— 属于结构性噪音。
    active_ids = {p.get("id") for p in data if p.get("status") == "active"}
    dropped = [i for i in issues if i.get("id") not in active_ids]
    if dropped:
        print(f"  [SKIP] {len(dropped)} 条告警来自非 active 条目，已忽略："
              f"{', '.join(str(i.get('id')) for i in dropped)}")
        issues = [i for i in issues if i.get("id") in active_ids]

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    stale = _stale_entries(data)
    report = {
        "version": "v2",
        "scan_date": date.today().isoformat(),
        "total_platforms": len(data),
        "issues_found": len(issues),
        "issues": issues,
        # 陈旧核验只进报告（CI 出 ::warning::），不建 Issue、不影响退出码：
        # 否则 22 条里有 17 条 verified_at 过期，会天天刷同一条单。
        "stale_found": len(stale),
        "stale": stale,
    }
    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nScan complete: {len(issues)} issues found")
    print(f"Report saved to {REPORT_FILE}")
    for issue in issues:
        print(f"  ! {issue['name']}: {issue['issue']} ({issue['detail']})")

    if stale:
        names = "、".join(f"{s['name']}（{s['reason']}）" for s in stale[:6])
        more = f" 等 {len(stale)} 条" if len(stale) > 6 else ""
        print(f"::warning::{len(stale)} 条 active 条目超过 {STALE_DAYS} 天未复核：{names}{more}",
              file=sys.stderr)

    # 有问题时退出码 1，便于 CI 判断是否建 Issue
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
