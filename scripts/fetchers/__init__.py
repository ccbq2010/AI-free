"""多源信息抓取器。

每个 fetcher 返回 list[RawCandidate]，统一由 check_sources.py 汇总去重。
"""

from dataclasses import dataclass, field


@dataclass
class RawCandidate:
    """从信息源发现的原始候选条目。"""
    source: str           # 来源标识，如 "github:xx025/carrot"
    name: str             # 平台/活动名称（可能不完整）
    benefit: str          # 福利描述片段
    raw: str              # 原始文本
    url: str = ""         # 相关链接（如有）
    keywords: list = field(default_factory=list)  # 命中的关键词


# 中英文关键词白名单 —— 命中其一才认为是"免费 AI 资源"
KEYWORDS = [
    # 中文
    "免费", "赠送", "白嫖", "薅羊毛", "福利", "礼包", "领", "送",
    "token", "tokens", "credit", "额度", "代金", "积分",
    # 英文
    "free", "bonus", "giveaway", "complimentary", "grant",
    "invite", "referral", "reward", "promo",
]


def matches_keywords(text: str) -> list[str]:
    """返回文本命中的所有关键词。"""
    text_lower = text.lower()
    return [kw for kw in KEYWORDS if kw.lower() in text_lower]


# RSS 等宽信息源用的「泛 AI」关键词（先捞进来，LLM 二次过滤）
AI_TOPIC_KEYWORDS = [
    # 中文泛 AI
    "大模型", "人工智能", "AI", "机器学习", "深度学习",
    "开源", "发布", "模型", "训练", "推理",
    "LangChain", "Agent", "RAG", "多模态", "AIGC",
    "GPT", "Claude", "Gemini", "Llama", "Qwen", "DeepSeek",
    "LLM", "AGI", "具身智能", "智能体", "MCP",
    # 中文产品名
    "OpenAI", "Anthropic", "谷歌", "百度AI", "阿里AI", "腾讯AI",
    "字节", "豆包", "文心", "通义", "盘古", "混元",
    "智谱", "MiniGLM", "ChatGLM", "百川", "月之暗面", "Kimi",
    "零一万物", "阶跃星辰", "DeepSeek", "面壁",
]
