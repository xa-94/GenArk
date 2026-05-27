"""HTTP 客户端 — 绕过系统代理"""

import os
import httpx


def _http_client(**kwargs) -> httpx.Client:
    """创建绕过代理的 httpx 客户端"""
    # 清除代理环境变量，httpx 会读取它们
    env = {}
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "all_proxy", "ALL_PROXY"):
        env[k] = os.environ.pop(k, None)
    client = httpx.Client(proxy=None, **kwargs)
    # 恢复
    for k, v in env.items():
        if v is not None:
            os.environ[k] = v
    return client
