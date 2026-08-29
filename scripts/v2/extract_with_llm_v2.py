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
  LLM_PROVIDERS               可选，JSON 数组，按序故障切换。推荐主备写法：
                [{"base_url":"https://api.longcat.chat/openai/v1","api_key":"...","model":"LongCat-2.0"},
                 {"base_url":"<备选供应商>","api_key":"...","model":"..."}]
                             选备胎原则：只收「无需信用卡绑定」的免费档，
                             需绑卡/付费开通的服务一律不收（Cerebras 实测 402 即此类）
  LLM_BASE_URL + LLM_API_KEY  兼容旧写法（单供应商），与 LLM_PROVIDERS 同时存在时排在后面
  LLM_MODEL                   旧写法的默认模型（LLM_PROVIDERS 里每项自带 model）

  原 GitHub Models 免费通道已于 2026-08 官方退役（410 Gone），勿再使用。
"""

from __future__ import annotations

import json
import os
import re
import sys

HIGH_CONFIDENCE = 0.8
LOW_CONFIDENCE = 0.5

DEFAULT_MODEL = "LongCat-2.0"


def get_providers() -> list[tuple[str, str, str]]:
    """返回 (base_url, api_key, model) 列表，按优先级排序。"""
    providers: list[tuple[str, str, str]] = []
    raw = os.environ.get("LLM_PROVIDERS", "").strip()
    if raw:
        try:
            for item in json.loads(raw):
                if item.get("base_url") and item.get("api_key"):
                    providers.append((
                        item["base_url"].rstrip("/"),
                        item["api_key"],
                        item.get("model") or DEFAULT_MODEL,
                    ))
        except json.JSONDecodeError:
            print("[WARN] LLM_PROVIDERS 不是合法 JSON，已忽略", file=sys.stderr)
    base_url = os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("LLM_API_KEY")
    if base_url and api_key:
        providers.append((base_url.rstrip("/"), api_key,
                          os.environ.get("LLM_MODEL") or DEFAULT_MODEL))
    if not providers:
        print(
            "[ERROR] 缺少 LLM_PROVIDERS 或 LLM_BASE_URL + LLM_API_KEY（仓库 Secrets）。\n"
            "        推荐 LongCat（每天 10 万 Token）+ Cerebras 备份（长期每天 1M Token）：\n"
            '        LLM_PROVIDERS=[{"base_url":"https://api.longcat.chat/openai/v1",...},'
            '{"base_url":"https://api.cerebras.ai/v1",...}]',
            file=sys.stderr,
        )
        sys.exit(2)
    return providers


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
- url 必须是平台官网/活动页域名；若只能给出新闻/聚合/博客文章链接，
  has_new_user_benefit=false 且 confidence=0.3（汇总文章不是福利页本身）
- 汇总/榜单/攻略类文章（同时罗列多个平台的额度）→ has_new_user_benefit=false
"""


def call_llm(provider: tuple[str, str, str], text: str) -> dict | None:
    import httpx

    base_url, api_key, model = provider
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
        timeout=60,
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


def process_candidate(candidate: dict, providers: list[tuple[str, str, str]],
                      start_idx: int) -> tuple[dict | None, int]:
    """依次尝试供应商（从上次成功的开始），返回 (结果, 成功供应商下标)。"""
    text = (
        f"来源: {candidate.get('source', '')}\n"
        f"名称: {candidate.get('name', '')}\n"
        f"描述: {candidate.get('benefit', '')}\n"
        f"链接: {candidate.get('url', '')}\n"
        f"原文: {candidate.get('raw', '')}"
    )
    last_err: Exception | None = None
    for offset in range(len(providers)):
        idx = (start_idx + offset) % len(providers)
        try:
            result = call_llm(providers[idx], text)
        except Exception as e:  # noqa: BLE001
            print(f"    [WARN] provider#{idx} ({providers[idx][0]}) 失败: {e}", file=sys.stderr)
            last_err = e
            continue
        # 请求成功但输出不可解析属模型输出问题，不再换供应商
        return result, idx
    raise last_err or RuntimeError("所有 LLM 供应商均失败")


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
        result = None
        for provider in get_providers():
            try:
                result = call_llm(provider, text)
                break
            except Exception as e:  # noqa: BLE001
                print(f"[WARN] provider {provider[0]} 失败: {e}", file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False, indent=2) if result else "{}")
        return

    candidates = json.loads(sys.stdin.read())
    if not isinstance(candidates, list):
        candidates = candidates.get("new_candidates", [])

    providers = get_providers()
    print(f"Processing {len(candidates)} candidates with LLM (v2)...", file=sys.stderr)
    print(f"LLM providers (failover order): {[p[0] for p in providers]}", file=sys.stderr)

    high: list[dict] = []
    low: list[dict] = []
    rejected = 0
    ok_idx = 0
    for i, c in enumerate(candidates):
        print(f"  [{i+1}/{len(candidates)}] {c.get('name', '?')[:40]}", file=sys.stderr)
        try:
            result, ok_idx = process_candidate(c, providers, ok_idx)
        except Exception as e:  # noqa: BLE001
            print(f"    [WARN] LLM call failed: {e}", file=sys.stderr)
            continue
        if result is None:
            rejected += 1
            continue
        result["_source"] = c.get("source", "")
        result["_raw"] = c.get("raw", "")[:200]
        result["_original_url"] = c.get("url", "")
        result["_original_name"] = c.get("name", "")
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
