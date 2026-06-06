"""钉钉推送器"""

import httpx
import json

from .http_client import _http_client
from .config import DINGTALK_WEBHOOK_URL


AGENT_DISPLAY_NAMES = {
    "xiangai": "祥霭分身",
    "guyuan": "顾远",
    "heming": "赫明",
    "shoushan": "守山",
}


def push_report(report: dict) -> bool:
    """将单智能体日报推送到钉钉，返回是否成功"""
    stats = report["stats"]
    agent_name = AGENT_DISPLAY_NAMES.get(
        report["agent_id"], report["agent_id"]
    )

    title = f"📊 GenArk 日报 · {report['date']} · {agent_name}"
    text = f"# {title}\n\n{report['narrative']}"

    if report["event_refs"]:
        refs = "、".join(report["event_refs"][:5])
        text += f"\n\n> 引用：{refs}"

    if report["llm_model"]:
        text += f"\n\n> 模型：{report['llm_model']} · tokens：{report['llm_tokens']}"

    return _send_markdown(title, text)


def push_composed(composed: dict) -> bool:
    """推送拼版日报到钉钉。

    拼版日报本身就是完整的 Markdown 文本，直接推送。
    与单人日报不同，拼版每日只推一条。
    """
    date = composed.get("date", "?")
    agents = composed.get("agents") or []
    names = [AGENT_DISPLAY_NAMES.get(a, a) for a in agents]
    title = f"GenArk 日报 · {date} · {'·'.join(names)}"

    text = f"# 📊 {title}\n\n{composed['narrative']}"

    return _send_markdown(title, text)


def push_text(message: str) -> bool:
    """发送纯文本消息到钉钉（通知/告警用）"""
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


def _send_markdown(title: str, text: str) -> bool:
    """发送 Markdown 消息到钉钉"""
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
