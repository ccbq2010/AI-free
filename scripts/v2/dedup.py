"""v2 平台身份归一与去重。

解决的问题（2026-10 复盘）：
  1. 旧的 `slugify()` 用 `re.sub(r"[^a-z0-9]+", "-", name)`，中文会被整体删掉，
     只剩名字里夹带的英文片段 —— 「百度千帆·大模型服务及Agent开发平台」→ `agent`、
     「…免费Tokens额度」→ `tokens`、「…免费额度」→ `unknown`，同一平台变成多个 id。
  2. 去重只看「已合并的 platforms-v2/v1」，不看仍未合并的 bot/v2-auto-* PR，
     于是 PR 不合 → 数据里没有 → 第二天原样再提一遍，无限堆积。

本模块只做纯计算 + 一个只读的 PR 枚举，不写任何文件。
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Callable
from urllib.parse import urlparse

# ── 常量 ────────────────────────────────────────────────

# 剥掉的子域名前缀（www.cloud.xxx 之类），只剥一次层
GENERIC_LABELS = {
    "www", "cloud", "docs", "doc", "api", "platform", "open",
    "console", "dev", "app", "m", "cn", "asia", "en",
}

# URL 路径里没有辨识度的段
GENERIC_SEGMENTS = {
    "s", "p", "doc", "docs", "index", "home", "login", "signin",
    "signup", "sign-up", "invite", "join", "joinus", "pricing",
    "price", "zh", "en", "cn", "api", "v1", "v2", "events",
    "event", "blog", "news", "detail", "about",
    # 资讯页常见路径：活动页 URL 形如 /article/12345，
    # 不剥掉会把「火山引擎 article」当成平台辨识名（doubao-student 曾得到
    # volcengine-article 这种 id）。
    "article", "articles", "post", "posts", "story", "stories", "read",
}

# 不能单独当 id 的泛词（模型名/通用词，中文名剥完常只剩这些）
GENERIC_SLUGS = {
    "agent", "agents", "token", "tokens", "api", "apis", "platform",
    "platforms", "model", "models", "free", "unknown", "app", "apps",
    "ai", "cloud", "doc", "docs", "login", "signup", "pricing",
    "invite", "join", "index", "home", "beta", "new", "pro", "plus",
}

# 二级公共后缀
MULTI_SUFFIX = {
    "com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn", "co.uk",
    "co.jp", "com.hk", "com.tw", "com.sg",
}

# 名称归一时剥掉的营销后缀（可迭代追加）
NAME_NOISE_SUFFIXES = (
    "新用户免费额度", "新用户免费tokens", "新用户免费", "邀请码活动",
    "注册送体验额度", "免费额度", "邀请码", "邀请活动", "注册送",
    "活动", "福利",
)


# ── slug 生成 ───────────────────────────────────────────

def _latin_slug(text: str) -> str:
    """取文本里的拉丁片段，丢掉纯数字段。"""
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    parts = [p for p in s.split("-") if p and not p.isdigit()]
    return "-".join(parts)[:40]


def _has_distinctive_part(slug: str) -> bool:
    """拉丁片段是否有辨识度。

    只判「整串是否在泛词表」不够：泛词拼起来同样没信息量，例如
    「百度千帆·大模型服务及Agent开发平台免费Tokens额度」的拉丁片段是
    `agent-tokens`，整串不在表里，但每一段都是泛词 —— 这会把同一个平台
    又切成多个 id，正是本模块要消灭的问题。要求至少一个 ≥3 字符的非泛词段。
    """
    if not slug or slug in GENERIC_SLUGS:
        return False
    return any(len(p) >= 3 and p not in GENERIC_SLUGS for p in slug.split("-") if p)


def _sld(netloc: str) -> str:
    """取域名主体（剥离 www/cloud/docs 等前缀，处理 com.cn 这类二级后缀）。"""
    host = (netloc or "").split(":")[0].lower()
    labels = [x for x in host.split(".") if x]
    while len(labels) > 2 and labels[0] in GENERIC_LABELS:
        labels.pop(0)
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_SUFFIX:
        core = labels[-3]
    elif len(labels) >= 2:
        core = labels[-2]
    else:
        core = labels[0] if labels else ""
    return re.sub(r"[^a-z0-9]+", "-", core).strip("-")


def _path_hint(url: str) -> str:
    """取 URL 路径里第一个有辨识度的段（跳过 doc/s/invite 与哈希段）。"""
    path = urlparse(url or "").path.lower()
    for seg in (x for x in path.split("/") if x):
        if seg in GENERIC_SEGMENTS or seg.isdigit():
            continue
        # 形如 imi2rpirg / ab12cd34 的哈希段
        if len(seg) >= 6 and re.fullmatch(r"[a-z0-9]+", seg) and re.search(r"\d", seg):
            continue
        cleaned = re.sub(r"[^a-z0-9]+", "-", seg).strip("-")
        if len(cleaned) >= 3 and cleaned not in GENERIC_SLUGS:
            return cleaned
    return ""


def slugify(name: str, url: str = "") -> str:
    """生成平台 id。

    优先级：
      1. 名字里的拉丁片段（≥3 字符且非泛词）—— 「SceneMint Pro」→ scenemint-pro
      2. 域名主体 + 首个路径段 —— 「百度千帆…」+ cloud.baidu.com/doc/qianfan → baidu-qianfan
      3. 仅域名主体
      4. p-<hash> 兜底
    """
    latin = _latin_slug(name)
    if _has_distinctive_part(latin):
        return latin[:40]

    netloc = urlparse(url or "").netloc.lower()
    sld = _sld(netloc)
    hint = _path_hint(url) if url else ""
    if sld and hint and hint != sld:
        return f"{sld}-{hint}"[:40]
    if sld:
        return sld[:40]
    if latin:
        return latin[:40]
    return "p-" + hashlib.sha1(f"{name}{url}".encode()).hexdigest()[:8]


# ── 名称归一与近似判定 ──────────────────────────────────

def name_key(name: str) -> str:
    """归一化平台名：去标点/空格 + 剥常见营销后缀。"""
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", (name or "").lower())
    for suf in NAME_NOISE_SUFFIXES:
        s = s.replace(suf, "")
    return s


def _is_cjk(s: str) -> bool:
    return any("\u4e00" <= c <= "\u9fff" for c in s)


def is_same_platform(a: str, b: str) -> bool:
    """两个归一化名是否指向同一平台。

    相等，或一方是另一方前缀。前缀判定的最短长度按字符信息密度分档：
    拉丁名要 ≥4 字符（避免 `qwen`/`qw` 这类短语误伤），中文名 2 字即可
    （「智谱」vs「智谱GLM」是同一家，2 字阈值不降会漏判，中文品牌普遍很短）。
    """
    if not a or not b:
        return False
    if a == b:
        return True
    if not (a.startswith(b) or b.startswith(a)):
        return False
    need = 2 if (_is_cjk(a) or _is_cjk(b)) else 4
    return min(len(a), len(b)) >= need


# ── 未合并 PR 里的条目 ──────────────────────────────────

PR_BRANCH_PREFIX = "bot/v2-auto-"
DATA_PATH = "data/platforms-v2.json"


def open_pr_entries(api: Callable[[str, str], Any], data_path: str = DATA_PATH) -> list[dict]:
    """枚举所有 open 的 bot/v2-auto-* PR 分支里的平台条目。

    `api(method, path)` 由调用方注入（各自的 GITHUB_TOKEN / repo 封装）。
    任何失败都 fail-open 返回已收集到的部分，绝不让巡检因此中断。
    """
    try:
        prs = api("GET", "/pulls?state=open&per_page=100")
    except Exception as e:  # noqa: BLE001
        print(f"  [dedup] 读取 open PR 失败，跳过未合并去重: {e}")
        return []

    out: list[dict] = []
    for pr in prs if isinstance(prs, list) else []:
        head = ((pr or {}).get("head") or {}).get("ref", "")
        if not head.startswith(PR_BRANCH_PREFIX):
            continue
        try:
            blob = api("GET", f"/contents/{data_path}?ref={head}")
            entries = json.loads(base64.b64decode(blob["content"]).decode("utf-8"))
        except Exception:  # noqa: BLE001
            continue  # 分支已删 / 文件不存在 → 跳过
        if isinstance(entries, list):
            out.extend(x for x in entries if isinstance(x, dict))
    return out


# ── 去重主逻辑 ─────────────────────────────────────────

def build_universe(entries: list[dict]) -> tuple[set[str], set[str], list[str]]:
    """把条目列表压成三个索引：id 集合 / 域名集合 / 归一化名列表。"""
    ids: set[str] = set()
    domains: set[str] = set()
    keys: list[str] = []
    for e in entries:
        if e.get("id"):
            ids.add(e["id"])
        url = e.get("url") or ""
        if url:
            d = urlparse(url).netloc.lower()
            if d:
                domains.add(d)
        k = name_key(e.get("name") or "")
        if k:
            keys.append(k)
    return ids, domains, keys
