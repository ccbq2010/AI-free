"""OpenRouter Models API 抓取器。

检测新上线的免费模型。
API: https://openrouter.ai/api/v1/models
"""

import json
from . import RawCandidate, matches_keywords
from .http import fetch

API_URL = "https://openrouter.ai/api/v1/models"


def fetch_all() -> list[RawCandidate]:
    """获取所有免费模型（pricing prompt == 0）。"""
    print("  Fetching OpenRouter models...")
    data = fetch(API_URL)
    if data is None:
        return []

    try:
        models = json.loads(data).get("data", [])
    except Exception as e:
        print(f"    [WARN] JSON parse failed: {e}")
        return []

    candidates = []
    for m in models:
        pricing = m.get("pricing", {})
        prompt_price = float(pricing.get("prompt", -1))
        completion_price = float(pricing.get("completion", -1))

        # 只关心完全免费的模型
        if prompt_price != 0 or completion_price != 0:
            continue

        model_id = m.get("id", "")
        name = m.get("name", model_id)
        context_length = m.get("context_length", 0)
        description = m.get("description", "")[:120]

        line = f"Free model: {name} — {description} ({context_length} ctx)"
        kws = matches_keywords(line + " " + description)
        # 免费模型天然命中"free"关键词
        if not kws:
            kws = ["free"]

        candidates.append(RawCandidate(
            source="openrouter:models",
            name=name[:80],
            benefit=f"Free | context: {context_length} | {description}",
            raw=line[:200],
            url=f"https://openrouter.ai/models/{model_id.split('/')[-1]}",
            keywords=kws,
        ))

    print(f"    Found {len(candidates)} free models")
    return candidates
