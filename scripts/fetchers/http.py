"""共享 HTTP 工具 —— 统一超时、重试、错误处理。"""

import httpx
from functools import lru_cache

__all__ = ["fetch", "fetch_text", "HEADERS"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AIFreeBot/1.0; "
        "+https://github.com/free-ai-free/free-ai-free)"
    ),
    "Accept": "application/vnd.github.v3.raw, text/plain, */*",
}

# 全局复用连接池
_client = httpx.Client(
    headers=HEADERS,
    timeout=15,
    follow_redirects=True,
)


def fetch(url: str, max_bytes: int = 2 * 1024 * 1024) -> bytes | None:
    """GET 请求，返回 bytes 或 None（失败时）。"""
    try:
        resp = _client.get(url)
        resp.raise_for_status()
        return resp.content[:max_bytes]
    except Exception as e:
        import sys
        print(f"  [WARN] fetch failed {url}: {e}", file=sys.stderr)
        return None


def fetch_text(url: str, max_bytes: int = 2 * 1024 * 1024) -> str | None:
    """GET 请求，返回解码后的文本。"""
    data = fetch(url, max_bytes)
    if data is None:
        return None
    return data.decode("utf-8", errors="replace")
