"""v2 共享 HTTP 工具 —— 直接复用 v1 的实现，保持行为一致。

注意：本模块命名为 http_util.py 而非 http.py，
避免遮蔽 Python 标准库 http 包（httpx 依赖它）。
"""

import sys
from pathlib import Path

# 让 scripts/ 成为可导入路径，复用 v1 fetchers.http
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))

from fetchers.http import HEADERS, fetch, fetch_text  # noqa: E402,F401

__all__ = ["fetch", "fetch_text", "HEADERS"]
