"""搜索引擎发现源（v2 新增）——吃社交平台内容的「二次分发层」。

小红书 / 公众号 / 即刻 / 知乎等平台的羊毛帖会被搜索引擎索引，
本源对「发现型关键词」跑搜索，把聚合文章捞回来，交给 LLM 抽取出
平台名、官方 URL 和福利描述。解决「老产品出新福利」在聚合仓库/
新品监控里看不到的盲区。

后端（均无需 API key，失败自动降级）：
  1. DuckDuckGo lite（实测对发现型查询相关性最好；同 IP 高频会触发限流）
  2. SearXNG 公共实例（独立代理 IP 池，DDG 限流时的替代通道）
  3. Bing 网页版（兜底；反爬时会返回与查询无关的固定结果，
     保留但只在前端结果不足时启用）

过滤分两层：
  - 宽网：命中 免费类宽词 且属于 AI 话题，或直接命中福利白名单
  - 严格把关交给下游 LLM 抽取（has_new_user_benefit + confidence）
"""

from __future__ import annotations

import base64
import os
import re
import time
from datetime import datetime
from urllib.parse import parse_qs, urlparse

import httpx
from selectolax.parser import HTMLParser

from .. import RawCandidate, is_new_user_benefit_candidate, matches_topic

# 发现型查询词：聚合文章是这类信息的主要载体；带年月防陈旧。
# 措辞经实测校准：DDG 对「注册送/薅羊毛/汇总」类措辞召回最好
DISCOVERY_QUERIES = [
    "AI 平台 新用户 注册送 token 免费额度",
    "免费 AI 大模型 API 额度 汇总 攻略",
    "AI 编程 工具 白嫖 免费 额度",
]

# 宽网词：发现源比其他源宽松，严格判断交给下游 LLM
_RELAX_WORDS = ["免费", "白嫖", "体验金", "代金券", "羊毛", "赠送"]

# 部分聚合文章标题不含 AI 话题词（如「Token 薅羊毛攻略」），补 AI 相关 hints
_TOPIC_HINTS = ["token", "api", "额度", "大模型", "积分"]

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_client = httpx.Client(headers=_BROWSER_HEADERS, timeout=15, follow_redirects=True)

_WS_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()


def _decode_bing_redirect(href: str) -> str:
    """Bing 结果链接是 /ck/a?...&u=a1<base64url> 形式的跳转，解出真实 URL。"""
    if "/ck/a" not in href:
        return href
    qs = parse_qs(urlparse(href).query).get("u", [""])[0]
    if not qs:
        return href
    payload = qs[2:] if qs.startswith("a1") else qs
    payload += "=" * (-len(payload) % 4)
    try:
        return base64.urlsafe_b64decode(payload).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return href


def _decode_ddg_redirect(href: str) -> str:
    """DDG lite 结果链接是 /l/?uddg=<urlencoded> 形式的跳转。"""
    if "//duckduckgo.com/l/" not in href and href.startswith("/l/"):
        href = "https://duckduckgo.com" + href
    if "/l/" not in href:
        return href
    target = parse_qs(urlparse(href).query).get("uddg", [""])[0]
    return target or href


def _search_bing(query: str) -> list[tuple[str, str, str]]:
    """返回 [(title, url, snippet)]。"""
    try:
        resp = _client.get(
            "https://www.bing.com/search",
            params={"q": query, "mkt": "zh-CN", "count": "20"},
        )
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"    [SKIP] bing failed: {e}")
        return []
    tree = HTMLParser(resp.text)
    out: list[tuple[str, str, str]] = []
    for node in tree.css("li.b_algo"):
        a = node.css_first("h2 a")
        if a is None:
            continue
        title = _clean(a.text())
        url = _decode_bing_redirect(a.attributes.get("href", ""))
        snip_node = node.css_first(".b_caption p") or node.css_first("p")
        snippet = _clean(snip_node.text()) if snip_node else ""
        if title and url.startswith("http"):
            out.append((title, url, snippet))
    return out


# SearXNG 公共实例（多数实例对公共访问限流，仅作尝试性通道）
_SEARX_INSTANCES = [
    "https://searx.be",
    "https://search.hbubli.cc",
]


def _search_serper(query: str) -> list[tuple[str, str, str]]:
    """Serper.dev 付费 API（免费档 2500 次/月）。配置 SERPER_API_KEY 时优先使用。"""
    key = os.environ.get("SERPER_API_KEY", "")
    if not key:
        return []
    try:
        resp = _client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": key, "Content-Type": "application/json"},
            json={"q": query, "gl": "cn", "hl": "zh-cn", "num": 15},
        )
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"    [SKIP] serper failed: {e}")
        return []
    out: list[tuple[str, str, str]] = []
    for item in resp.json().get("organic", []):
        title = _clean(item.get("title", ""))
        url = item.get("link", "")
        snippet = _clean(item.get("snippet", ""))
        if title and url:
            out.append((title, url, snippet))
    return out


def _search_searxng(query: str) -> list[tuple[str, str, str]]:
    for base in _SEARX_INSTANCES:
        try:
            resp = _client.get(
                f"{base}/search",
                params={"q": query, "language": "zh-CN"},
                timeout=10,
            )
            resp.raise_for_status()
        except Exception:  # noqa: BLE001
            continue
        tree = HTMLParser(resp.text)
        out: list[tuple[str, str, str]] = []
        for node in tree.css("article.result, div.result"):
            a = node.css_first("h3 a") or node.css_first("a")
            if a is None:
                continue
            title = _clean(a.text())
            url = a.attributes.get("href", "")
            snip_node = node.css_first("p.content")
            snippet = _clean(snip_node.text()) if snip_node else ""
            if title and url.startswith("http"):
                out.append((title, url, snippet))
        if out:
            return out
    return []


def _search_ddg(query: str) -> list[tuple[str, str, str]]:
    try:
        # POST 方式比 GET 更不易触发 DDG 限流
        resp = _client.post("https://html.duckduckgo.com/html/", data={"q": query})
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        print(f"    [SKIP] ddg failed: {e}")
        return []
    tree = HTMLParser(resp.text)
    out: list[tuple[str, str, str]] = []
    for node in tree.css("div.result"):
        a = node.css_first("a.result__a")
        if a is None:
            continue
        title = _clean(a.text())
        url = _decode_ddg_redirect(a.attributes.get("href", ""))
        snip_node = node.css_first("a.result__snippet")
        snippet = _clean(snip_node.text()) if snip_node else ""
        if title and url.startswith("http"):
            out.append((title, url, snippet))
    return out


def _keep(title: str, snippet: str) -> bool:
    text = f"{title} {snippet}"
    if is_new_user_benefit_candidate(text)[0]:
        return True
    text_lower = text.lower()
    topic_hit = bool(matches_topic(text)) or any(h in text_lower for h in _TOPIC_HINTS)
    if not topic_hit:
        return False
    return any(w in text for w in _RELAX_WORDS)


def fetch_all() -> list[RawCandidate]:
    month_tag = datetime.now().strftime("%Y年%m月")
    queries = DISCOVERY_QUERIES + [f"免费 AI 额度 注册送 {month_tag}"]
    candidates: list[RawCandidate] = []
    seen_urls: set[str] = set()

    print(f"    queries: {len(queries)}")
    for q in queries:
        results = _search_serper(q)
        backend = "serper" if results else ""
        if not results:
            results = _search_ddg(q)
            backend = "ddg"
        if len(results) < 3:
            results = results + _search_searxng(q)
            backend += "+searx" if results else ""
        if len(results) < 3:
            # 最后 Bing 兜底；注意 Bing 反爬时会返回与查询无关的固定结果，
            # 交给 _keep 过滤即可
            results = results + _search_bing(q)
            backend += "+bing" if results else ""
        kept = 0
        for title, url, snippet in results:
            if url in seen_urls:
                continue
            if not _keep(title, snippet):
                continue
            seen_urls.add(url)
            candidates.append(RawCandidate(
                source=f"SearchEngine:{backend}",
                name=title[:100],
                benefit=snippet[:200],
                raw=f"{title} {snippet}",
                url=url,
            ))
            kept += 1
        print(f"    [{backend:>9s}] {q!r:<40s} -> {len(results)} raw, {kept} kept")
        time.sleep(3)  # 查询间隔，降低限流概率

    print(f"    SearchEngine total: {len(candidates)}")
    return candidates
