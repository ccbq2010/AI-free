#!/usr/bin/env python3
"""过期检测脚本。

对 platforms.json 中每个 url 做 HEAD 请求 + 轻量内容检查，
标记可能已过期的平台。

输出 data/review_expiry_report.json，供 build.py 在页面上显示警告。
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime, date
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).parent
ROOT = SCRIPT_DIR.parent
DATA_FILE = ROOT / "data" / "platforms.json"
REPORT_FILE = ROOT / "data" / "expiry_report.json"
TIMEOUT_SECONDS = 20

sys.path.insert(0, str(SCRIPT_DIR))
from fetchers.http import fetch, fetch_text, _client  # noqa: E402


# 页面中如果出现这些词，说明活动已结束
EXPIRED_MARKERS = [
    "已结束", "已过期", "活动结束", "已截止", "已下架",
    "expired", "ended", "no longer available", "closed",
    "sold out", "已抢完", "已领完",
]


def check_url_status(url: str) -> dict:
    """检查 URL 状态，返回 {status, reason}。

    对 timeout 做一次 fallback：改用 GET + stream 模式读取第一个 bytes，
    这对 HEAD 超时但 GET 正常的站点更宽容。
    """
    if not url:
        return {"status": "unknown", "reason": "no url"}

    try:
        resp = _client.head(url, timeout=TIMEOUT_SECONDS, follow_redirects=True)
        # 部分站点 HEAD 返回 404 但 GET 正常，此时 fallback 到 GET
        if resp.status_code == 404:
            try:
                get_resp = _client.get(url, timeout=TIMEOUT_SECONDS, follow_redirects=True)
                if get_resp.status_code == 200:
                    resp = get_resp
            except Exception:
                pass  # 保留 HEAD 的 404 结果
    except Exception:
        # HEAD 抛异常，fallback 至 GET
        try:
            resp = _client.get(url, timeout=TIMEOUT_SECONDS, follow_redirects=True)
        except Exception as e:
            return {"status": "error", "reason": str(e)[:100]}

    if resp.status_code == 404:
        return {"status": "dead", "reason": "HTTP 404"}
    if resp.status_code >= 500:
        return {"status": "error", "reason": f"HTTP {resp.status_code}"}
    if resp.status_code >= 400:
        return {"status": "warning", "reason": f"HTTP {resp.status_code}"}
    return {"status": "ok", "reason": f"HTTP {resp.status_code}"}


def check_page_content(url: str) -> dict | None:
    """轻量内容检查：抓取前 5KB 搜索过期标记。"""
    text = fetch_text(url, max_bytes=5 * 1024)
    if text is None:
        return None

    text_lower = text.lower()
    for marker in EXPIRED_MARKERS:
        if marker.lower() in text_lower:
            return {"expired_marker": marker}
    return None


def check_deadline(platform: dict) -> str | None:
    """检查 deadline 字段是否已过期。"""
    deadline = platform.get("deadline")
    if not deadline:
        return None

    # 尝试解析日期
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"]:
        try:
            d = datetime.strptime(deadline, fmt).date()
            if d < date.today():
                return f"deadline {deadline} passed"
            return None
        except ValueError:
            continue

    # 无法解析的日期格式（如"每月可领"）跳过
    return None


def check_referral_code_in_url(platform: dict) -> str | None:
    """检查含推荐码的平台，code 是否仍在 URL 中。"""
    from urllib.parse import unquote
    ref = platform.get("referral", {})
    code = ref.get("code", "")
    rtype = ref.get("type", "none")
    if rtype not in ("invite_code", "referral_link", "ref_code", "invite_link") or not code:
        return None
    url = platform.get("url", "")
    if code not in unquote(url):
        return f"referral code '{code}' not found in URL"
    return None


def scan_all() -> list[dict]:
    """扫描所有平台，返回需要关注的条目。"""
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    issues = []

    for p in data:
        pid = p.get("id", "")
        name = p.get("name", "")
        url = p.get("url", "")

        print(f"  Checking {name}...")

        # 1. 检查 deadline
        deadline_issue = check_deadline(p)
        if deadline_issue:
            issues.append({
                "id": pid,
                "name": name,
                "issue": "deadline_passed",
                "detail": deadline_issue,
            })

        # 2. 检查 URL 状态
        url_status = check_url_status(url)
        if url_status["status"] in ("dead", "error"):
            issues.append({
                "id": pid,
                "name": name,
                "issue": "url_" + url_status["status"],
                "detail": url_status["reason"],
            })

        # 3. 检查页面内容（仅对 active 状态）
        if p.get("status") == "active" and url_status["status"] == "ok":
            content_check = check_page_content(url)
            if content_check:
                issues.append({
                    "id": pid,
                    "name": name,
                    "issue": "content_expired",
                    "detail": f"found marker: {content_check['expired_marker']}",
                })

        # 4. 检查推荐码是否仍在 URL 中
        ref_issue = check_referral_code_in_url(p)
        if ref_issue:
            issues.append({
                "id": pid,
                "name": name,
                "issue": "referral_code_mismatch",
                "detail": ref_issue,
            })

    return issues


def main():
    print("=" * 50)
    print("AI-free expiry scanner")
    print("=" * 50)

    issues = scan_all()

    report = {
        "scan_date": date.today().isoformat(),
        "total_platforms": 0,
        "issues_found": len(issues),
        "issues": issues,
    }

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    report["total_platforms"] = len(data)

    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n✅ Scan complete: {len(issues)} issues found")
    print(f"   Report saved to {REPORT_FILE}")

    if issues:
        for issue in issues:
            print(f"  ⚠️  {issue['name']}: {issue['issue']} ({issue['detail']})")


if __name__ == "__main__":
    main()
