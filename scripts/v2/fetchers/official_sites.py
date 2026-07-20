"""AI 平台官网 Pricing/活动页抓取器（v2 新增）。

策略：
  1. 维护一份「已知 AI 平台官网活动页」清单（pricing / events / invite 页）。
  2. 抓取页面文本，用 v2 白名单精准匹配新用户福利线索。
  3. 只产出白名单命中的候选；已收录域名在主脚本中再过滤。

页面结构差异大，这里不做结构化解析，只截取命中关键词的上下文片段，
交给下游 LLM 做结构化抽取。
"""

from __future__ import annotations

import re

from .. import RawCandidate, is_new_user_benefit_candidate
from ..http_util import fetch_text

# 已知 AI 平台的活动/pricing 页（持续扩充）
# 格式: (平台名, URL)
OFFICIAL_PAGES: list[tuple[str, str]] = [
    # 国内大模型
    ("智谱开放平台", "https://open.bigmodel.cn/pricing"),
    ("DeepSeek", "https://platform.deepseek.com/usage"),
    ("通义千问", "https://bailian.console.aliyun.com/"),
    ("百度千帆", "https://qianfan.cloud.baidu.com/"),
    ("火山方舟", "https://www.volcengine.com/product/ark"),
    ("讯飞星火", "https://xinghuo.xfyun.cn/"),
    ("Kimi 开放平台", "https://platform.moonshot.cn/"),
    ("MiniMax", "https://platform.minimaxi.com/"),
    ("阶跃星辰", "https://platform.stepfun.com/"),
    ("零一万物", "https://platform.lingyiwanwu.com/"),
    ("商汤日日新", "https://platform.sensenova.cn/"),
    # AI IDE / 编程
    ("Trae", "https://www.trae.ai/pricing"),
    ("CodeBuddy", "https://www.codebuddy.cn/"),
    # 海外
    ("OpenRouter", "https://openrouter.ai/"),
    ("Together AI", "https://www.together.ai/pricing"),
    ("Fireworks AI", "https://fireworks.ai/pricing"),
    ("Groq", "https://groq.com/pricing/"),
    ("Cerebras", "https://www.cerebras.ai/"),
    ("Mistral", "https://mistral.ai/pricing"),
    ("Cohere", "https://cohere.com/pricing"),
]

# 去掉 HTML 标签的极简清洗
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def _html_to_text(html: str) -> str:
    """粗暴地把 HTML 转成纯文本（去 script/style/标签，压缩空白）。"""
    text = _SCRIPT_RE.sub(" ", html)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text)


def _extract_snippets(text: str, window: int = 160) -> list[str]:
    """截取白名单关键词命中的上下文片段。"""
    from .. import WHITELIST_KEYWORDS

    snippets: list[str] = []
    lower = text.lower()
    seen: set[str] = set()
    for kw in WHITELIST_KEYWORDS:
        start = 0
        kw_lower = kw.lower()
        while True:
            idx = lower.find(kw_lower, start)
            if idx == -1:
                break
            lo = max(0, idx - window // 2)
            hi = min(len(text), idx + window // 2)
            snippet = text[lo:hi].strip()
            if snippet not in seen:
                seen.add(snippet)
                snippets.append(snippet)
            start = idx + len(kw_lower)
            if len(snippets) >= 10:  # 单页面上限，防爆量
                return snippets
    return snippets


def fetch_all() -> list[RawCandidate]:
    """扫描所有官网活动页，返回白名单命中的候选。"""
    candidates: list[RawCandidate] = []
    for name, url in OFFICIAL_PAGES:
        print(f"  Fetching official page: {name} ({url})...")
        html = fetch_text(url, max_bytes=1024 * 1024)
        if html is None:
            print("    [SKIP] fetch failed")
            continue
        text = _html_to_text(html)
        ok, white, _black = is_new_user_benefit_candidate(text)
        if not ok:
            print("    [SKIP] no whitelist keywords")
            continue
        snippets = _extract_snippets(text)
        for snip in snippets[:5]:  # 每站点最多 5 条候选
            ok2, white2, _ = is_new_user_benefit_candidate(snip)
            if not ok2:
                continue
            candidates.append(RawCandidate(
                source=f"official:{name}",
                name=name,
                benefit=snip[:120],
                raw=snip[:300],
                url=url,
                keywords=white2,
            ))
        print(f"    Found {min(len(snippets), 5)} snippets")
    return candidates
