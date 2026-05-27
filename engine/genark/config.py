import os
from pathlib import Path

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 智能体实例路径映射
AGENT_INSTANCES = {
    "guyuan": "/home/hermes/.hermes-pm",
    "heming": "/home/hermes/.hermes-genboz",
    "shoushan": "/home/hermes/.hermes",
}

# 数据库
DB_PATH = str(DATA_DIR / "genark.db")

# DeepSeek（独立 Key）
DEEPSEEK_API_KEY = os.getenv("GENARK_DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# 钉钉
DINGTALK_WEBHOOK_URL = os.getenv("GENARK_DINGTALK_WEBHOOK", "")

# 采集配置
COLLECT_FILE_GLOB = "*.jsonl"  # 只采集 JSONL，跳过 Cron JSON

# 日报配置
REPORT_RETRY_COUNT = 3
REPORT_FALLBACK_TO_DATA_ONLY = True  # LLM 失败时降级为纯数据


def agent_home(agent_id: str) -> str:
    """获取智能体的 Hermes 实例根目录"""
    path = AGENT_INSTANCES.get(agent_id)
    if not path:
        raise ValueError(f"Unknown agent: {agent_id}. Available: {list(AGENT_INSTANCES.keys())}")
    return path


def agent_sessions_dir(agent_id: str) -> str:
    return os.path.join(agent_home(agent_id), "sessions")


def agent_memories_dir(agent_id: str) -> str:
    return os.path.join(agent_home(agent_id), "memories")


def agent_skills_dir(agent_id: str) -> str:
    return os.path.join(agent_home(agent_id), "skills")
