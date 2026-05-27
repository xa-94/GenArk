"""LLM 日报生成器"""

import json
import httpx
from datetime import datetime

from .http_client import _http_client
from .config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL
from .config import REPORT_RETRY_COUNT, REPORT_FALLBACK_TO_DATA_ONLY
from .db import get_conn
from .state_computer import compute_daily_stats, get_event_summaries

AGENT_PROFILES = {
    "guyuan": {
        "name": "顾远",
        "role": "GenBoz 产品经理，负责 PRD 维护和产品架构设计。思维缜密，善于从用户需求中提炼产品方案。",
    },
    "heming": {
        "name": "赫明",
        "role": "GenBoz Tech Lead，负责技术架构、安全审计和代码实现。务实严谨，先方案后执行。",
    },
    "shoushan": {
        "name": "守山",
        "role": "祥霭的主智能体，陪伴创始人成长的伙伴。负责基础设施运维、多智能体协调，是团队三角的枢纽。",
    },
}


def _build_prompt(agent_id: str, stats: dict, summaries: list[dict], yesterday_report: str | None) -> str:
    """构造日报 Prompt"""
    profile = AGENT_PROFILES.get(agent_id, {"name": agent_id, "role": "智能体"})

    events_text = ""
    for s in summaries[:25]:  # 最多 25 条
        events_text += f"  [{s['event_id']}] {s['time']} {s['type']}: {s['summary']}\n"

    yesterday_section = ""
    if yesterday_report:
        yesterday_section = f"\n## 昨日日报（对比参考）\n{yesterday_report[:500]}\n"

    prompt = f"""你是一个观察者，正在为智能体「{profile['name']}」撰写今天的日报。
{profile['name']}是{profile['role']}

## 今日数据
- 会话: {stats['sessions']} 次
- 消息: {stats['messages_sent']} 条
- 工具调用: {stats['tool_calls']} 次，成功率 {stats['tool_success_rate']}
- 记忆更新: {stats['memory_changes']} 次
- 技能变化: {stats['skill_changes']} 次
- 最活跃时段: {stats['peak_hour']}
- 总事件: {stats['total_events']} 条
{yesterday_section}
## 今日关键事件（按时间序）
{events_text if events_text else '(今日无事件)'}

## 要求
1. 用叙事语气撰写，像一个人在讲述另一个人的一天
2. 重点关注：有趣的事、成长迹象、值得记录的瞬间
3. 长度控制在 200-400 字
4. 每个事实后标注引用，格式：【evt_xxx】
5. 不要编造数据中没有的事
6. 不要用项目符号，写连贯的段落
7. 如果今日无事件，如实说「今天很安静」就好，不要编造

## 格式
📊 数字面板
（用一行简洁列出今日关键数字）

🧠 今日叙事
（叙事正文）
"""
    return prompt


def _call_llm(prompt: str) -> dict:
    """调用 DeepSeek API，返回 {content, tokens}"""
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 800,
        "temperature": 0.7,
    }

    with _http_client(timeout=60) as client:
        resp = client.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "tokens": data.get("usage", {}).get("total_tokens", 0),
        }


def generate_report(agent_id: str, date: str | None = None) -> dict:
    """生成日报，返回 {id, narrative, stats, ...} 或降级版本"""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    stats = compute_daily_stats(agent_id, date)
    summaries = get_event_summaries(agent_id, date)

    # 获取昨日日报
    with get_conn() as conn:
        yesterday = conn.execute(
            "SELECT narrative FROM daily_reports WHERE agent_id = ? AND report_date < ? ORDER BY report_date DESC LIMIT 1",
            (agent_id, date),
        ).fetchone()
        yesterday_text = yesterday["narrative"] if yesterday else None

    prompt = _build_prompt(agent_id, stats, summaries, yesterday_text)

    # 尝试 LLM 生成
    narrative = None
    llm_model = None
    llm_tokens = 0
    for attempt in range(REPORT_RETRY_COUNT):
        try:
            result = _call_llm(prompt)
            narrative = result["content"]
            llm_model = DEEPSEEK_MODEL
            llm_tokens = result["tokens"]
            break
        except Exception as e:
            if attempt == REPORT_RETRY_COUNT - 1:
                if REPORT_FALLBACK_TO_DATA_ONLY:
                    narrative = _fallback_report(stats)
                else:
                    raise

    # 提取 event 引用
    event_refs = []
    if narrative:
        import re
        event_refs = re.findall(r"evt_\d{8}_\d{6}", narrative)

    report_id = f"report_{date.replace('-', '')}"
    report = {
        "id": report_id,
        "agent_id": agent_id,
        "date": date,
        "stats": stats,
        "narrative": narrative,
        "event_refs": event_refs,
        "llm_model": llm_model,
        "llm_tokens": llm_tokens,
    }
    return report


def _fallback_report(stats: dict) -> str:
    """LLM 失败时的降级纯数据日报"""
    return f"""📊 数字面板
会话 {stats['sessions']} 次 | 消息 {stats['messages_sent']} 条 | 工具 {stats['tool_calls']} 次 | 活跃时段 {stats['peak_hour']}

🧠 今日叙事
（今日叙事生成失败，仅展示数据摘要。）
"""


def save_report(report: dict) -> None:
    """保存日报到数据库"""
    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO daily_reports
               (id, agent_id, report_date, stats_json, narrative, event_refs, llm_model, llm_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                report["id"],
                report["agent_id"],
                report["date"],
                json.dumps(report["stats"], ensure_ascii=False),
                report["narrative"],
                json.dumps(report["event_refs"], ensure_ascii=False),
                report["llm_model"],
                report["llm_tokens"],
            ),
        )
