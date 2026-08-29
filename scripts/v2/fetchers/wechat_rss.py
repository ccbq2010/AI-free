"""微信公众号 RSS 桥（v2 新增）。

微信生态没有公开 API，直接抓取不可行；社区桥接服务把公众号更新
转成标准 RSS 后即可程序化消费。订阅**平台官方号**（智谱 AI、
腾讯 CodeBuddy、硅基流动、火山引擎等）可第一时间拿到活动公告——
比等第三方转载快，也比爬小红书可靠。

配置：data/wechat_rss.json
  {
    "feeds": [
      {"name": "智谱AI", "url": "https://wechat2rss.xlab.app/feed/<id>.xml"}
    ]
  }

生成订阅：打开 wechat2rss.xlab.app → 搜索公众号 → 生成 RSS →
把 feed 地址填进上面数组。feeds 为空时本源静默跳过，不影响管线。
"""

from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path

from .. import RawCandidate, is_new_user_benefit_candidate, matches_topic
from ..http_util import fetch_text

CONFIG = Path(__file__).resolve().parent.parent.parent / "data" / "wechat_rss.json"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_html(text: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", unescape(text or ""))).strip()


def _load_feeds() -> list[dict]:
    if not CONFIG.exists():
        return []
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        return [f for f in cfg.get("feeds", []) if f.get("url")]
    except (json.JSONDecodeError, AttributeError):
        print("    [WARN] wechat_rss.json 格式错误，忽略")
        return []


def _fetch_feed(feed: dict) -> list[RawCandidate]:
    import feedparser

    name = feed.get("name") or feed["url"]
    text = fetch_text(feed["url"], max_bytes=2 * 1024 * 1024)
    if text is None:
        print(f"    [SKIP] {name} feed fetch failed")
        return []
    parsed = feedparser.parse(text)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        print(f"    [SKIP] {name} feed 解析失败")
        return []

    candidates: list[RawCandidate] = []
    for entry in parsed.entries[:20]:
        title = _clean_html(entry.get("title", ""))
        summary = _clean_html(entry.get("summary", "") or entry.get("description", ""))[:300]
        link = entry.get("link", "")
        text = f"{title} {summary}"
        if not title:
            continue
        # 官号公告里「免费/活动」类宽网词 + 福利白名单，双层放行
        if is_new_user_benefit_candidate(text)[0]:
            pass
        elif not (matches_topic(text) and any(
                w in text for w in ("免费", "白嫖", "福利", "赠送", "活动", "体验"))):
            continue
        candidates.append(RawCandidate(
            source=f"WeChatRSS:{name}",
            name=title[:100],
            benefit=summary[:200],
            raw=text,
            url=link,
        ))
    return candidates


def fetch_all() -> list[RawCandidate]:
    feeds = _load_feeds()
    if not feeds:
        print("    [SKIP] wechat_rss.json 未配置订阅源")
        return []

    candidates: list[RawCandidate] = []
    for feed in feeds:
        got = _fetch_feed(feed)
        print(f"    [{feed.get('name', '?')}] {len(got)} candidates")
        candidates.extend(got)
    print(f"    WeChatRSS total: {len(candidates)}")
    return candidates
