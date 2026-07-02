#!/usr/bin/env python3
"""Generate index.html and qr.html from data/platforms.json."""

import json
from datetime import datetime
from pathlib import Path
from string import Template

import qrcode
from qrcode.image.svg import SvgPathImage

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "platforms.json"
TPL_INDEX = ROOT / "templates" / "index.html"
TPL_QR = ROOT / "templates" / "qr.html"


def load_platforms() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


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


def main():
    platforms = load_platforms()
    active = [p for p in platforms if p.get("status") == "active"]
    glm_count = sum(1 for p in active if any("GLM-5.2" in t for t in p.get("tags", [])))
    now = datetime.now().strftime("%Y年%m月%d日")

    deadlines = [
        {"name": p["name"], "display": fmt_date(p["deadline"])}
        for p in active if p.get("deadline")
    ]

    # Pre-generate QR SVGs
    qr_data = {}
    for p in active:
        qr_data[p["id"]] = qr_svg_inline(p["url"])

    # Build index.html
    tpl = Template(TPL_INDEX.read_text(encoding="utf-8"))
    dl_html = "".join(
        f'<div class="deadline-item">⏰ {d["name"]} {d["display"]}截止</div>'
        for d in deadlines
    )
    html = tpl.substitute(
        _platforms_json=json.dumps(active, ensure_ascii=False, indent=2),
        total=str(len(active)),
        glm_count=str(glm_count),
        updated_at=now,
        _deadlines=dl_html,
    )
    (ROOT / "index.html").write_text(html, encoding="utf-8")

    # Build qr.html
    tpl2 = Template(TPL_QR.read_text(encoding="utf-8"))
    html2 = tpl2.substitute(
        _platforms_json=json.dumps(active, ensure_ascii=False, indent=2),
        _qr_data_json=json.dumps(qr_data, ensure_ascii=False),
        total=str(len(active)),
        glm_count=str(glm_count),
        updated_at=now,
    )
    (ROOT / "qr.html").write_text(html2, encoding="utf-8")

    print(f"Generated index.html and qr.html ({len(active)} platforms).")


if __name__ == "__main__":
    main()
