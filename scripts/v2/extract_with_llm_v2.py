#!/usr/bin/env python3
"""v2 LLM 结构化抽取 —— 聚焦「新用户专属福利」。

与 v1（scripts/extract_with_llm.py）的差异：
  - 输出新增 has_new_user_benefit (bool) 字段
  - prompt 明确收录/排除标准（注册即送/新人专享/首单免费 vs. 本身免费）
  - 输出按 confidence 分桶：>=0.8 高置信（自动 PR），0.5-0.8 低置信（Issue），<0.5 丢弃

用法：
  python scripts/v2/extract_with_llm_v2.py < candidates.json > extracted_v2.json
  python scripts/v2/extract_with_llm_v2.py --text "某平台注册即送1000积分"

环境变量：
  LLM_BASE_URL + LLM_API_KEY  优先，任意 OpenAI-compatible API（自建/第三方）
  GITHUB_TOKEN                回退，走 GitHub Models（GA 端点 models.github.ai）
                             ——workflow 须授予 `permissions: models: read`，否则 401
  LLM_MODEL                   显式 API 默认 gpt-4o-mini；GitHub Models 默认 openai/gpt-4o-mini
"""

from __future__ import annotations

import json
import os
import re
import sys

HIGH_CONFIDENCE = 0.8
LOW_CONFIDENCE = 0.5


def get_client() -> tuple[str, str, str]:
    # 优先使用显式配置的 OpenAI-compatible API（自建/第三方），便于覆盖默认。
    base_url = os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("LLM_API_KEY")
    if base_url and api_key:
        return (base_url, api_key, os.environ.get("LLM_MODEL", "gpt-4o-mini"))
    # 回退到 GitHub Models（GA 端点，零成本）。
    # 注意：调用方 workflow 必须授予 `permissions: models: read`，否则 401。
    # 端点须用 https://models.github.ai/inference，模型名须带 openai/ 前缀。
    gh_token = os.environ.get("GITHUB_TOKEN")
    if gh_token:
        return (
            "https://models.github.ai/inference",
            gh_token,
            os.environ.get("LLM_MODEL", "openai/gpt-4o-mini"),
        )
    print("[ERROR] 需要 LLM_BASE_URL + LLM_API_KEY 或 GITHUB_TOKEN", file=sys.stderr)
    sys.exit(2)


SYSTEM_PROMPT = """你是一个 AI 平台「新用户福利」信息抽取助手。

【收录标准】只收录：AI 平台向**新注册用户**提供的专属福利，例如：
- 注册即送积分 / token / 代金券 / 免费额度
- 新人专享礼包、首单免费 / 立减
- 邀请码 / referral 双方奖励
- 限期免费试用（free trial / welcome credit）

【排除标准】以下情况不属于「新用户专属福利」：
- 产品本身免费、开源、无需注册即可使用（无新用户专属动作）
- 无注册门槛的免费 tier SaaS
- 破解、共享账号、拼车
- 与 AI 平台无关的内容

从用户提供的文本中提取以下字段，严格按 JSON 输出：
{
  "name": "平台/活动名称（简短）",
  "provider": "厂商/背景（一句话，可留空字符串）",
  "benefit": "福利描述（一句话，含具体数额）",
  "url": "官网或活动页链接（如无则空字符串）",
  "deadline": "截止日期 YYYY-MM-DD（如无则 null）",
  "has_new_user_benefit": true/false,
  "confidence": 0.0-1.0,
  "tags": ["标签1", "标签2"]
}

判断规则：
- 文本明确描述新用户注册福利 → has_new_user_benefit=true
- 只是"本身免费/开源/无需注册" → has_new_user_benefit=false
- 与 AI 平台福利无关 → has_new_user_benefit=false 且 confidence=0
- 信息不完整、无法确认时，降低 confidence 而不是猜测
"""


def call_llm(base_url: str, api_key: str, model: str, text: str) -> dict | None:
    import httpx

    resp = httpx.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        },
        timeout=30,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", content, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                return None
        return None


def process_candidate(candidate: dict, client: tuple[str, str, str]) -> dict | None:
    base_url, api_key, model = client
    text = (
        f"来源: {candidate.get('source', '')}\n"
        f"名称: {candidate.get('name', '')}\n"
        f"描述: {candidate.get('benefit', '')}\n"
        f"链接: {candidate.get('url', '')}\n"
        f"原文: {candidate.get('raw', '')}"
    )
    result = call_llm(base_url, api_key, model, text)
    if result is None:
        return None
    result["_source"] = candidate.get("source", "")
    result["_raw"] = candidate.get("raw", "")[:200]
    result["_original_url"] = candidate.get("url", "")
    result["_original_name"] = candidate.get("name", "")
    return result


def bucket(result: dict) -> str:
    """按 has_new_user_benefit + confidence 分桶。"""
    if not result.get("has_new_user_benefit"):
        return "rejected"
    conf = result.get("confidence", 0) or 0
    try:
        conf = float(conf)
    except (TypeError, ValueError):
        return "rejected"
    if conf >= HIGH_CONFIDENCE:
        return "high"
    if conf >= LOW_CONFIDENCE:
        return "low"
    return "rejected"


def main() -> None:
    if "--text" in sys.argv:
        idx = sys.argv.index("--text")
        text = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if not text:
            print("用法: --text '文本内容'")
            sys.exit(1)
        result = call_llm(*get_client(), text)
        print(json.dumps(result, ensure_ascii=False, indent=2) if result else "{}")
        return

    candidates = json.loads(sys.stdin.read())
    if not isinstance(candidates, list):
        candidates = candidates.get("new_candidates", [])

    print(f"Processing {len(candidates)} candidates with LLM (v2)...", file=sys.stderr)
    client = get_client()

    high: list[dict] = []
    low: list[dict] = []
    rejected = 0
    for i, c in enumerate(candidates):
        print(f"  [{i+1}/{len(candidates)}] {c.get('name', '?')[:40]}", file=sys.stderr)
        try:
            result = process_candidate(c, client)
        except Exception as e:  # noqa: BLE001
            print(f"    [WARN] LLM call failed: {e}", file=sys.stderr)
            continue
        if result is None:
            rejected += 1
            continue
        b = bucket(result)
        if b == "high":
            high.append(result)
        elif b == "low":
            low.append(result)
        else:
            rejected += 1

    output = {
        "version": "v2",
        "total_input": len(candidates),
        "high_confidence": high,
        "low_confidence": low,
        "rejected_count": rejected,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\nDone: {len(high)} high, {len(low)} low, {rejected} rejected.",
          file=sys.stderr)


if __name__ == "__main__":
    main()
