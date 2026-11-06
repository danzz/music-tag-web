---
name: music-tag-web
description: 音乐曲库智能管理技能：自动化巡检音频标签与结构、剥离广告与脏字符、精准甄别同名/Live/翻唱版本、执行批量打标与规范化目录重构整理。
---

# 🎵 Music Tag Web - 音乐曲库智能管理技能

本技能指导 Agent 作为专业的**数字音乐与有声课程馆藏员（Music & Audiobook Curator）**，通过调用 `music_tag_cli.py` 工具与底层 `Music Tag Web` 服务进行高性能交互。

---

## 一、 系统架构与极速交互原则

- **底座定位**：`Music Tag Web` 是服务端的**数据查询与磁盘安全执行引擎**。所有高耗时的打标、图片压缩与文件移动均以**异步任务（Batch Tasks）**模式在后台运行，防止磁盘 I/O 阻塞。
- **【极速交互黄金法则】严禁逐首小步试探**：
  外部大模型每次 Tool Call 往返均产生 2~4 秒的通信与推理延迟。**绝对禁止逐首调用 `search` 或逐首调用 `fetch_lyric`**！
- **优先采用全并发批处理**：
  必须优先使用 `auto-plan` 指令，将多轮往返压缩为 **2 步闭环**（生成方案 $\to$ 审查提交），耗时从数十秒骤降至 1 秒内！

---

## 二、 ⚡ 极速两步作业流（High-Speed Workflow，首选推荐）

对任何文件夹进行智能整理，一律执行以下标准两步：

### 第一步：一键全并发预规划（One-Shot Auto-Plan）
运行 `auto-plan`，系统自动根据目录特征智能分流（音乐模式 vs 得到课程模式）：
```bash
# 自动探测或显式指定 --type auto|music|course
python3 scripts/music_tag_cli.py auto-plan /app/media/01_精选专辑 -o /tmp/plan.json
```
- **音乐模式**：多线程全并发检索官方音乐源，消歧正规录音室专辑、Live 版、翻唱版本，预取歌词与高清封面；
- **课程模式**：纯本地毫秒级离线解析，根据目录名提取讲师与课程，剥离广告杂质，提取并格式化音轨号；
- **耗时**：音乐模式约 0.3s~1.5s，课程模式仅需 **0.05s**！

---

### 第二步：审查裁决与一键安全落盘（One-Shot Apply）
Agent 快速浏览 `plan.json`，确认无误后直接一键提交落盘：
```bash
# 提交并等待异步线程池落盘，自动刷新曲库缓存
python3 scripts/music_tag_cli.py apply-plan /tmp/plan.json --wait
```
- 底层异步任务中心通过独立磁盘写入线程池安全写入 ID3 标签、保存同名 `.lrc` 歌词与封面图片；
- 自动触发缓存清理，Web 工作台即刻呈现最新状态。

---

## 三、 📚 得到课程与有声书专属整理准则（Course Mode）

当用户要求整理“得到课程”、“有声书”、“播客”或目录名包含 `·` / `讲` / `课` 时，系统自动启用课程模式：

1. **目录名讲师与课程提取**：
   - `32_万维钢·精英日课6` $\to$ 讲师（`artist`/`albumartist`）：`万维钢`，课程（`album`）：`精英日课6`；
   - `刘润·商业洞察力30讲` $\to$ 讲师：`刘润`，课程：`商业洞察力30讲`；
   - `薛兆丰的经济学课` $\to$ 讲师：`薛兆丰`，课程：`经济学课`；
   - `[吴军] 谷歌方法论` $\to$ 讲师：`吴军`，课程：`谷歌方法论`。
2. **文件名音轨号与纯净标题清洗**：
   - 提取音轨：`01 发刊词...`、`第02讲丨怎样做出好决策...`、`003_科学思考...` $\to$ 音轨号写入 `tracknumber`（两位补零 `01, 02`，百讲以上三位补零 `001`）；
   - 彻底剥离标题中的各种引流括号广告：如 `【关注微信公众号：xxx】`、`[买课加V：1234]`、`（认准微信abc）`；
   - 标题字段（`title`）保持纯粹节目名（如 `发刊词：什么是现代精英的底层逻辑`）。
3. **元数据深度净化**：
   - 清空被网盘贩子污染的 `comment` 描述（统一重置为 `得到音频课程 (已净化)`）；
   - 流派（`genre`）统一设置为 `Audiobook`；
   - 优先检测并内嵌目录下的本地封面文件（`cover.jpg` / `cover.png`）。

---

## 四、 细粒度操作命令集（备用）

| 目的 | 指令 | 说明 |
| :--- | :--- | :--- |
| **快速体检** | `python3 scripts/music_tag_cli.py inspect <path>` | 统计缺失字段、脏字符与重复项 |
| **单曲搜索** | `python3 scripts/music_tag_cli.py search "<title>" --resource kugou` | 支持 `kugou/qmusic/netease/migu` |
| **手动提交** | `python3 scripts/music_tag_cli.py submit-tags --dir <path> --wait < update.json` | 提交自定义标签 JSON 批次 |
| **自动刮削** | `python3 scripts/music_tag_cli.py submit-auto-tag --dir <path> --wait` | 触发底层规则刮削引擎 |
| **目录规整** | `python3 scripts/music_tag_cli.py submit-tidy --root /app/media --src-dir <dir> --first-dir artist --second-dir album` | 按讲师/课程多级目录归档 |
| **刷新缓存** | `python3 scripts/music_tag_cli.py refresh-cache --path <path>` | 强制重新扫描磁盘更新缓存 |
