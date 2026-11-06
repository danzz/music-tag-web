# 🎵 Music Tag Web - Agent Skill

本目录包含为外部成熟 Agent Harness（如 Antigravity、Claude Code、Cursor、OpenHands、Dify 等）量身打造的 **Music Tag Web 音乐曲库智能管理技能**。

---

## 🌟 核心理念与架构

- **零依赖与极简底座**：`Music Tag Web` 服务端保持纯粹与轻量，负责 NAS 本地文件安全 I/O 与多线程异步任务批处理；
- **Agent Harness 驱动**：思考、语义推理、版本消歧（Live / 翻唱 / 录音室版甄别）、广告字符清洗等由外部成熟的 Agent Harness 驱动；
- **极速全并发预规划（Auto-Plan）**：将传统 10+ 次的单步往返压缩为 **2 步闭环**（并发生成方案 $\to$ 审查提交），耗时在 1~2 秒内。

---

## 🛠️ 文件结构

```text
skills/music-tag-web/
├── SKILL.md                 # Agent 核心技能指引（极速两步作业法与消歧准则）
└── README.md                # 本使用说明

scripts/
├── music_tag_cli.py         # 供 Agent 调用的标准化数据查询与任务提交 CLI & Python SDK
└── test_agent_skill_integration.py # 端到端集成验证脚本
```

---

## 🚀 极速作业模式（推荐）

```bash
# 1. 一键全并发预规划 (生成全目录多源检索、封面歌词预抓取方案，耗时 < 1s)
python3 scripts/music_tag_cli.py auto-plan /app/media/01_精选专辑 -o /tmp/plan.json

# 2. 一键应用方案 (提交异步线程池安全落盘，自动刷新缓存)
python3 scripts/music_tag_cli.py apply-plan /tmp/plan.json --wait
```
