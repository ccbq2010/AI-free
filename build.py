#!/usr/bin/env python3
"""Generate index.html, qr.html, feed.xml, and api.json from data/platforms.json."""

import json
import html
import argparse
from datetime import datetime
from pathlib import Path
from string import Template

import qrcode
from qrcode.image.svg import SvgPathImage

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "platforms.json"
TPL_INDEX = ROOT / "templates" / "index.html"
TPL_QR = ROOT / "templates" / "qr.html"
SITE_URL = "https://ccbq2010.github.io/AI-free"

# 数据源映射：v1=原 platforms.json（遗留），v2=自动发现管线产出 platforms-v2.json
SOURCE_FILES = {"v1": "platforms.json", "v2": "platforms-v2.json"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate AI-free site from platform data."
    )
    parser.add_argument(
        "--source",
        choices=list(SOURCE_FILES.keys()),
        default="v1",
        help="数据来源：v1=platforms.json（遗留默认），v2=platforms-v2.json（自动发现管线）。"
        "线上站点自 v2 上线后由 build.yml 传 --source v2。",
    )
    return parser.parse_args()


def load_platforms() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def validate_platform(p: dict, index: int) -> list[str]:
    """返回平台数据的问题列表，空表示通过。"""
    issues = []
    if not p.get("id"):
        issues.append(f"missing 'id'")
    if not p.get("name"):
        issues.append(f"missing 'name'")
    if not p.get("url"):
        issues.append(f"missing 'url'")
    if not p.get("benefit"):
        issues.append(f"missing 'benefit'")
    # benefit 如果是 markdown 链接格式，简单提醒
    benefit = p.get("benefit", "")
    if benefit.startswith("[") or benefit.startswith("http"):
        issues.append(f"benefit looks like raw markdown/url: {benefit[:40]}")
    return issues


def qr_svg_inline(url: str) -> str:
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
        image_factory=SvgPathImage,
    )
    qr.add_data(url)
    qr.make(fit=True)
    svg = qr.make_image().to_string(encoding="unicode")
    if svg.startswith("<?xml"):
        svg = svg.split("?>", 1)[1].strip()
    return svg


def fmt_date(date_str):
    if not date_str:
        return ""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y年%m月%d日")
    except ValueError:
        return date_str


def with_utm(platform: dict, utm: str) -> dict:
    """返回平台数据的浅拷贝，其 url 追加 UTM 参数；原 dict 不变。"""
    p = dict(platform)
    raw = p.get("url", "")
    if raw:
        joiner = "&" if "?" in raw else "?"
        p["url"] = f"{raw}{joiner}{utm}"
    return p


def build_featured_html(featured: list[dict]) -> str:
    """生成 top "隐藏大额" 专区的 HTML 片段 — 复用主卡片网格布局，通过琥珀色左边框+背景高亮区分。"""
    cards = []
    for i, p in enumerate(featured, 1):
        name = html.escape(p["name"])
        provider = html.escape(p.get("provider", ""))
        benefit = p.get("benefit", "")
        highlights = p.get("benefit_highlight", [])
        benefit_html = _apply_highlights(benefit, highlights)
        url = html.escape(p.get("url", "#"))
        cards.append(
            f'<a class="feat-card" href="{url}" data-pid="{p["id"]}" target="_blank" rel="noopener">'
            f'<span class="feat-index">💎 {str(i).rjust(1)}</span>'
            f'<div class="feat-body">'
            f'<div class="feat-name">{name}</div>'
            f'<div class="feat-provider">{provider}</div>'
            f'<div class="feat-benefit">🎁 {benefit_html}</div>'
            f'</div>'
            f'<span class="feat-action pf-link">前往 →</span>'
            f'</a>'
        )
    return (
        '<section class="featured">\n'
        '  <div class="feat-title">💎 隐藏大额 · 新人优先</div>\n'
        + "\n".join(cards)
        + "\n</section>\n"
    )


def _apply_highlights(text: str, highlights: list[str]) -> str:
    """在文本中包裹高亮 <span class="hi">，不做 HTML 转义。"""
    if not text or not highlights:
        return html.escape(text or "")
    escaped = html.escape(text)
    for hl in (h for h in highlights if h):
        escaped = escaped.replace(html.escape(hl), '<span class="hi">' + html.escape(hl) + "</span>")
    return escaped


def validate_referral_urls(platforms: list[dict]) -> list[str]:
    """检查含推荐码的平台，code 是否出现在 url 中。返回问题列表。"""
    from urllib.parse import unquote
    issues = []
    for p in platforms:
        ref = p.get("referral", {})
        code = ref.get("code", "")
        rtype = ref.get("type", "none")
        if rtype not in ("invite_code", "referral_link", "ref_code", "invite_link") or not code:
            continue
        url = p.get("url", "")
        if code not in unquote(url):
            issues.append(f'  {p["name"]}: referral.code 不在 URL 中 (code={code})')
    return issues


def main():
    args = parse_args()
    global DATA_FILE
    DATA_FILE = ROOT / "data" / SOURCE_FILES[args.source]
    print(f"[build] source={args.source} -> {DATA_FILE.name}")

    platforms = load_platforms()

    # Schema 校验 — 在构建前拦截脏数据
    all_issues = []
    for i, p in enumerate(platforms):
        issues = validate_platform(p, i)
        for issue in issues:
            pid = p.get("id", f"index={i}")
            all_issues.append(f"  [{pid}] {issue}")
    if all_issues:
        print("⚠️ Schema 校验发现问题:")
        for line in all_issues:
            print(line)
        dirty_ids = {p.get("id") for p in platforms if validate_platform(p, -1)}
        platforms = [p for p in platforms if p.get("id") not in dirty_ids]
        print(f"   已跳过 {len(all_issues)} 个问题条目，继续构建剩余 {len(platforms)} 个")

    active = [p for p in platforms if p.get("status") == "active"]
    glm_count = sum(1 for p in active if any("GLM-5.2" in t for t in p.get("tags", [])))
    now = datetime.now().strftime("%Y年%m月%d日")
    subtitle = f"{len(active)} 个顶级 AI 平台免费额度 · 注册即领 · 每周验证更新"

    # 推荐码一致性校验
    ref_issues = validate_referral_urls(platforms)
    if ref_issues:
        print("⚠️ 推荐码 URL 不一致:")
        for line in ref_issues:
            print(line)

    # UTM suffixes for QR and RSS
    url_qr_suffix = "utm_source=ai-free&utm_medium=qr"
    active_qr = [with_utm(p, url_qr_suffix) for p in active]

    # Pre-generate QR SVGs
    qr_data = {}
    for p in active_qr:
        qr_data[p["id"]] = qr_svg_inline(p["url"])

    # Deadlines 折叠（<details> + <summary>）
    deadline_items = [
        (p["name"], fmt_date(p["deadline"]))
        for p in active if p.get("deadline")
    ]
    if deadline_items:
        items_html = "".join(
            f'<div class="deadline-item"><span class="dl-name">{name}</span>'
            f'<span class="dl-date">{date}</span></div>'
            for name, date in deadline_items
        )
        deadlines_html = (
            f'<details class="deadline-box"><summary>部分福利有截止时间 — 展开查看 ({len(deadline_items)} 项)</summary>'
            f'{items_html}</details>'
        )
    else:
        deadlines_html = ""

    # Build index.html — featured 由 JS 从 PLATFORMS_RAW 中按 tier 渲染
    tpl = Template(TPL_INDEX.read_text(encoding="utf-8"))
    html_out = tpl.safe_substitute(
        _platforms_raw_json=json.dumps(active, ensure_ascii=False, indent=2),
        total=str(len(active)),
        glm_count=str(glm_count),
        updated_at=now,
        subtitle=subtitle,
        _deadlines=deadlines_html,
        _featured="",  # JS-driven
    )
    (ROOT / "index.html").write_text(html_out, encoding="utf-8")

    # Build qr.html
    tpl2 = Template(TPL_QR.read_text(encoding="utf-8"))
    html2 = tpl2.safe_substitute(
        _platforms_json=json.dumps(active_qr, ensure_ascii=False, indent=2),
        _qr_data_json=json.dumps(qr_data, ensure_ascii=False),
        total=str(len(active)),
        glm_count=str(glm_count),
        updated_at=now,
    )
    (ROOT / "qr.html").write_text(html2, encoding="utf-8")

    # Build feed.xml (RSS 2.0) — 为已上架活跃平台生成订阅源
    build_feed(active)

    # Build api.json — 公开 JSON API（无 UTM 参数）
    build_api(active)

    print(f"Generated index.html, qr.html, feed.xml, api.json ({len(active)} platforms).")


def _xml_escape_url(url: str) -> str:
    """URL 放入 XML 元素时需双重转义：html.escape 处理 & → &amp;、< → &lt; 等。"""
    return html.escape(url, quote=True)


def build_feed(platforms: list[dict], utm: str = "utm_source=ai-free&utm_medium=rss"):
    """生成 RSS 2.0 feed.xml。"""
    now = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0800")
    items = []
    for p in platforms:
        name = html.escape(p["name"])
        provider = html.escape(p.get("provider", ""))
        benefit = html.escape(p.get("benefit", ""))
        raw_url = p.get("url", "")
        link = f"{raw_url}{('&' if '?' in raw_url else '?')}{utm}" if raw_url else SITE_URL
        link_xml = _xml_escape_url(link)
        desc = f"{provider} — { benefit}".strip(" —")
        items.append(
            "    <item>\n"
            f"      <title>{name}</title>\n"
            f"      <link>{link_xml}</link>\n"
            f"      <guid isPermaLink=\"false\">{p['id']}</guid>\n"
            f"      <pubDate>{now}</pubDate>\n"
            f"      <description>{html.escape(desc)}</description>\n"
            "    </item>"
        )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        '  <channel>\n'
        '    <title>AI 新用户福利合集</title>\n'
        f'    <link>{SITE_URL}/</link>\n'
        '    <description>新用户注册免费领 AI 额度 · 自动周更</description>\n'
        f'    <lastBuildDate>{now}</lastBuildDate>\n'
        f'    <itemCount>{len(items)}</itemCount>\n'
        + "\n".join(items)
        + "\n  </channel>\n"
        + "</rss>"
    )
    (ROOT / "feed.xml").write_text(xml, encoding="utf-8")


def build_api(platforms: list[dict]):
    """生成公开 api.json（纯净 URL，无 UTM），供第三方消费。"""
    api_data = {
        "site": SITE_URL,
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "count": len(platforms),
        "platforms": [
            {
                "id": p["id"],
                "name": p["name"],
                "provider": p.get("provider", ""),
                "benefit": p.get("benefit", ""),
                "url": p.get("url", ""),
                "tags": p.get("tags", []),
                "tier": p.get("tier", "normal"),
            }
            for p in platforms if p.get("status") == "active"
        ],
    }
    (ROOT / "api.json").write_text(
        json.dumps(api_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
