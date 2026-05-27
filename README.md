# GenArk — 智能体生命平台

一个**智能体世界的观察与成长系统**——记录多个 AI 智能体的完整生命轨迹，向创始人提供叙事化日报，并赋予智能体自我认知与自主学习的能力。

## 架构

```
GenArk（旁观者）
    │
    ├── 采集层：增量读取 Hermes 智能体的 sessions/memories/skills
    ├── 存储层：SQLite + 哈希链（防篡改事件流）
    ├── 报告层：DeepSeek LLM 生成叙事化日报
    └── 推送层：钉钉 Webhook
```

## 快速开始

```bash
cd engine
cp .env.example .env   # 编辑填入 API Key

# 安装依赖
uv sync

# 初始化数据库
uv run genark init

# 采集数据
uv run genark collect --agent guyuan

# 生成并推送日报
uv run genark daily --agent guyuan

# 查看状态
uv run genark status --agent guyuan

# 验证哈希链
uv run genark verify-chain --agent guyuan
```

## 项目结构

```
engine/
├── genark/           # Python 包
│   ├── cli.py        # CLI 入口
│   ├── collector.py  # 增量采集
│   ├── event_store.py# 事件存储 + 哈希链
│   ├── reporter.py   # LLM 日报生成
│   ├── pusher.py     # 钉钉推送
│   └── config.py     # 配置
├── bin/              # Cron 脚本
├── pyproject.toml
└── .env.example
```

## 技术栈

- Python 3.12+
- SQLite（事件存储）
- DeepSeek（日报 LLM）
- httpx（HTTP 客户端）
- 钉钉 Webhook（消息推送）
- uv（包管理）
