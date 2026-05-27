"""钉钉推送器"""

import httpx
import json

from .http_client import _http_client
from .config import DINGTALK_WEBHOOK_URL


def push_report(report: dict) -> bool:
    """将日报推送到钉钉，返回是否成功"""
    stats = report["stats"]
    agent_name = {"guyuan": "顾远", "heming": "赫明", "shoushan": "守山"}.get(
        report["agent_id"], report["agent_id"]
    )

    # 构造 Markdown 消息
    title = f"📊 GenArk 日报 · {report['date']} · {agent_name}"
    text = f"# {title}\n\n{report['narrative']}"

    if report["event_refs"]:
        refs = "、".join(report["event_refs"][:5])
        text += f"\n\n> 引用：{refs}"

    if report["llm_model"]:
        text += f"\n\n> 模型：{report['llm_model']} · tokens：{report['llm_tokens']}"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": text,
        },
    }

    try:
        with _http_client(timeout=10) as client:
            resp = client.post(
                DINGTALK_WEBHOOK_URL,
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            data = resp.json()
            return data.get("errcode") == 0
    except Exception:
        return False


def push_text(message: str) -> bool:
    """发送纯文本消息到钉钉（通知用）"""
    payload = {
        "msgtype": "text",
        "text": {"content": f"GenArk：{message}"},
    }
    try:
        with _http_client(timeout=10) as client:
            resp = client.post(
                DINGTALK_WEBHOOK_URL,
                headers={"Content-Type": "application/json"},
                json=payload,
            )
            data = resp.json()
            return data.get("errcode") == 0
    except Exception:
        return False
