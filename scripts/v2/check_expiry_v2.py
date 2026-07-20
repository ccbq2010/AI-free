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
    issues = _v1.scan_all()

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    report = {
        "version": "v2",
        "scan_date": date.today().isoformat(),
        "total_platforms": len(data),
        "issues_found": len(issues),
        "issues": issues,
    }
    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nScan complete: {len(issues)} issues found")
    print(f"Report saved to {REPORT_FILE}")
    for issue in issues:
        print(f"  ! {issue['name']}: {issue['issue']} ({issue['detail']})")

    # 有问题时退出码 1，便于 CI 判断是否建 Issue
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
