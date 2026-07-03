#!/usr/bin/env python3
"""LLM 辅助结构化抽取。

将原始候选文本转换为标准化 JSON：
{name, benefit, url, deadline, confidence, tags}

支持两种后端：
  1. GitHub Models（默认，Actions 内免费）
  2. 任意 OpenAI-compatible API（通过环境变量配置）

用法：
  python scripts/extract_with_llm.py < candidates.json > extracted.json
  python scripts/extract_with_llm.py --text "某平台送1000积分"
"""

import json
import os
import sys

# ── 配置 ────────────────────────────────────────────────

def get_client():
    """根据环境变量返回 (base_url, api_key, model)。"""
    # 优先 GitHub Models（Actions 内自动注入 GITHUB_TOKEN）
    gh_token = os.environ.get("GITHUB_TOKEN")
    if gh_token:
        return (
            "https://models.inference.ai.azure.com",
            gh_token,
            os.environ.get("LLM_MODEL", "gpt-4o-mini"),
        )

    # 回退：自定义 OpenAI-compatible API
    base_url = os.environ.get("LLM_BASE_URL")
    api_key = os.environ.get("LLM_API_KEY")
    model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    if not base_url or not api_key:
        print("[ERROR] 需要 GITHUB_TOKEN 或 LLM_BASE_URL + LLM_API_KEY", file=sys.stderr)
        sys.exit(2)

    return (base_url, api_key, model)


SYSTEM_PROMPT = """你是一个 AI 福利资源信息抽取助手。
从用户提供的文本中提取以下字段，严格按 JSON 输出：

{
  "name": "平台/活动名称（简短）",
  "benefit": "福利描述（一句话）",
  "url": "官网链接（如无则空字符串）",
  "deadline": "截止日期（如无则 null）",
  "confidence": 0.0-1.0,
  "tags": ["标签1", "标签2"]
}

confidence 表示你对该信息确实是"免费 AI 资源"的确信程度。
如果文本与免费 AI 资源无关，设 confidence=0。
"""


def call_llm(base_url: str, api_key: str, model: str, text: str) -> dict | None:
    """调用 LLM 返回结构化 JSON。"""
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
        # 尝试从 markdown 代码块中提取
        import re
        m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        return None


def process_candidate(candidate: dict) -> dict | None:
    """处理单个候选，返回结构化结果或 None。"""
    base_url, api_key, model = get_client()

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

    # 合并原始信息
    result["_source"] = candidate.get("source", "")
    result["_raw"] = candidate.get("raw", "")[:200]
    result["_original_url"] = candidate.get("url", "")

    return result


def main():
    if "--text" in sys.argv:
        # 单条测试模式
        idx = sys.argv.index("--text")
        text = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else ""
        if not text:
            print("用法: --text '文本内容'")
            sys.exit(1)
        base_url, api_key, model = get_client()
        result = call_llm(base_url, api_key, model, text)
        print(json.dumps(result, ensure_ascii=False, indent=2) if result else "{}")
        return

    # 批量模式：从 stdin 读取 candidates JSON
    candidates = json.loads(sys.stdin.read())
    if not isinstance(candidates, list):
        candidates = candidates.get("new_candidates", [])

    print(f"Processing {len(candidates)} candidates with LLM...", file=sys.stderr)

    results = []
    for i, c in enumerate(candidates):
        print(f"  [{i+1}/{len(candidates)}] {c.get('name', '?')[:40]}", file=sys.stderr)
        result = process_candidate(c)
        if result and result.get("confidence", 0) >= 0.5:
            results.append(result)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
