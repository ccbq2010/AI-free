"""v2 内容发现：精准关键词 + 反过滤黑名单。

与 v1（scripts/fetchers）并行，互不影响。
v2 的收录标准更严格：只收「AI 平台向新用户提供的注册福利」，
排除「本身免费但无新用户专属福利」的条目。
"""

from dataclasses import dataclass, field

# ── 精准关键词白名单 ─────────────────────────────────────
# 命中其一才进入下一轮（比 v1 的泛关键词严格得多）
WHITELIST_KEYWORDS = [
    # 中文 —— 明确指向「新用户专属」
    "注册即送", "新人专享", "新用户专享", "新用户福利", "新用户礼包",
    "新人福利", "新人礼包", "新手礼包", "新手福利", "首单免费",
    "首单立减", "首次注册", "注册送", "注册领", "注册有礼",
    "邀请码", "邀请有礼", "邀请奖励", "邀请好友",
    "新人券", "新客券", "新人代金券",
    # 英文 —— 明确指向 sign-up incentive
    "sign up bonus", "signup bonus", "sign-up bonus",
    "welcome credit", "welcome credits", "welcome bonus",
    "free trial", "start for free", "new user", "new users",
    "referral code", "referral bonus", "invite code", "invitation code",
    "first order free", "first month free",
]

# ── 反过滤黑名单 ─────────────────────────────────────────
# 命中这些词且不含白名单词 → 直接丢弃（开源工具、无注册门槛的免费 SaaS）
BLACKLIST_PATTERNS = [
    # 开源/自托管类 —— 没有「新用户注册福利」概念
    "open source", "开源", "self-hosted", "self hosted", "自部署", "本地部署",
    "github stars", "apache-2.0", "mit license",
    # 无门槛免费 tier（无新用户专属动作）
    "无需注册", "no sign up", "no signup", "no sign-up", "no registration",
    "免登录", "no login", "无需登录", "无需 api key", "no api key",
    "always free", "永久免费", "完全免费",
    # 破解/共享账号类（不合规，拒收）
    "破解", "crack", "共享账号", "拼车",
]

# 泛 AI 话题词（用于 RSS/社区源先捞宽网，LLM 二次过滤）
AI_TOPIC_KEYWORDS = [
    "大模型", "人工智能", "AI", "LLM", "Agent", "AIGC",
    "GPT", "Claude", "Gemini", "Llama", "Qwen", "DeepSeek", "Kimi",
    "智谱", "ChatGLM", "通义", "文心", "豆包", "混元", "阶跃星辰",
    "OpenAI", "Anthropic", "MiniMax", "月之暗面", "零一万物",
    "AI IDE", "AI 编程", "AI coding", "code assistant",
    "Cursor", "Copilot", "Windsurf", "Trae", "CodeBuddy",
]


@dataclass
class RawCandidate:
    """从信息源发现的原始候选条目（与 v1 结构兼容）。"""
    source: str
    name: str
    benefit: str
    raw: str
    url: str = ""
    keywords: list = field(default_factory=list)


def matches_whitelist(text: str) -> list[str]:
    """返回文本命中的白名单关键词。"""
    text_lower = text.lower()
    return [kw for kw in WHITELIST_KEYWORDS if kw.lower() in text_lower]


def matches_blacklist(text: str) -> list[str]:
    """返回文本命中的黑名单词。"""
    text_lower = text.lower()
    return [kw for kw in BLACKLIST_PATTERNS if kw.lower() in text_lower]


def matches_topic(text: str) -> list[str]:
    """返回文本命中的泛 AI 话题词。"""
    text_lower = text.lower()
    return [kw for kw in AI_TOPIC_KEYWORDS if kw.lower() in text_lower]


def is_new_user_benefit_candidate(text: str) -> tuple[bool, list[str], list[str]]:
    """v2 核心预过滤：白名单命中且未被黑名单否决。

    返回 (是否通过, 命中白名单, 命中黑名单)。
    规则：白名单命中 >=1 即通过；黑名单命中但白名单也命中时仍通过
    （交给 LLM 最终判断，例如「无需注册」出现在另有注册福利的文本中）。
    """
    white = matches_whitelist(text)
    if not white:
        return False, [], []
    black = matches_blacklist(text)
    return True, white, black
