# AI PC Daily Memory Agent Runbook

这是一份给本地 AI PC Agent / 评委环境 / 本地小模型阅读的统一入口。先读这份，再决定要跑离线 demo、真实钉钉、飞书、本地目录、Obsidian，还是本地 AI rerank 工具。

本包不依赖 Codex、Codex CLI、桌面便签 App 或云端模型。推荐运行方式是：本地 `<=35B` Agent 大脑调用这些脚本准备上下文，再由本地模型生成最终 `DailyResult`。赛事基准可用 Ollama + Qwen3.6-35B-A3B + QwenPaw/Trae；脚本本身只要求 Python 和本地文件/CLI。

## 1. 先判断当前环境

| 当前状态 | 应走路径 |
| --- | --- |
| 无网、无钉钉、无飞书 | 跑 `examples/demo-workday/`，验证完整链路。 |
| 有网，钉钉 `dws` 已登录 | 配置 `dingtalk`，拉取文档、表格、整天日程、待办。 |
| 有网，飞书 `lark-cli` 已登录 | 配置 `feishu`，拉取指定文档、妙记、日程、任务。 |
| 只有本地资料 | 配置 `localMarkdownDirs` 和/或 `obsidianVaults`，只读取明确目录。 |
| 有本地 embedding / OpenVINO | 在同步后额外跑 `local_ai_rerank.py`。 |
| 无本地模型 | 可以跑脚本和 mock demo；正式参赛结果仍应由本地模型生成。 |

任何路径都不要扫描 `/`、用户 home、全盘目录、所有云文档或所有知识库。只能读取配置文件里明确列出的目录、vault、URL、token、node id、时间范围和文件。

### 本地模型下载/转换脚本

评审基准如果已经提供 Ollama + Qwen3.6-35B-A3B，可以直接使用现有服务。若需要自行准备，可从仓库根目录运行：

```bash
python scripts/download_ollama_model.py --model qwen3.6-35b-a3b
```

如果 Ollama registry 中的模型名不同，请把 `--model` 改成实际名称，并同步设置：

```bash
export AIPC_LLM_BASE_URL=http://localhost:11434/v1
export AIPC_LLM_MODEL=<OLLAMA_MODEL_NAME>
```

OpenVINO embedding 模型可用脚本下载并转换成本地目录：

```bash
python -m pip install -r requirements-openvino.txt
python scripts/prepare_openvino_embedding.py \
  --model-id BAAI/bge-small-zh-v1.5 \
  --output models/openvino/bge-small-zh-v1.5
```

转换后用本地目录验证：

```bash
python scripts/verify_submission.py \
  --embedding-backend openvino \
  --embedding-model models/openvino/bge-small-zh-v1.5
```

这两个准备脚本都有 `--dry-run`，可在无网环境先检查实际命令。Ollama endpoint 必须是 localhost；OpenVINO rerank 只读取本地模型目录。

## 2. 最短可跑路径：离线 demo

这个路径不需要网络、钉钉、飞书、Codex 或本地模型，适合评委先验证 Skill 链路。

评委最短命令：

```bash
python scripts/verify_submission.py
```

这个命令会在临时目录里跑完整离线链路，并输出 `daily_context.md`、`wiki_context.md`、`local_rerank.json`、`mock_daily_result.json`、`final_daily_memory.md` 等文件路径。

```bash
cd examples/demo-workday
python ../../scripts/sync_work_memory.py --config config.json
python ../../scripts/local_ai_rerank.py \
  --memory-home .aipc-work-memory \
  --query "AI PC Skill 提交 今日会议 今天看的文章" \
  --backend token \
  --output out/local_rerank.json
```

生成后，本地 Agent 读取：

- `out/wiki_context.md`
- `out/daily_context.md`
- `out/daily_memory.md`
- `out/local_rerank.json`

然后按 `../agent_prompt.daily_result.md` 生成 `out/daily_result.json`，再执行：

```bash
python ../../scripts/validate_daily_result.py out/daily_result.json
python ../../scripts/save_daily_result.py \
  --input out/daily_result.json \
  --date 2026-06-09 \
  --markdown-output out/daily_memory.md
```

最终今日 memory 在 `out/daily_memory.md`；结构化结果在 `out/daily_result.json`。

## 3. 真实工作路径：先复制配置

从仓库根目录执行：

```bash
cp examples/work_memory_config.sample.json work_memory_config.local.json
```

编辑 `work_memory_config.local.json`：

- `date`：要整理的日期。
- `timezone`：例如 `Asia/Shanghai`。
- `memoryHome`：Skill 自己的本地记忆目录，例如 `.aipc-work-memory`。
- `localMarkdownDirs`：只放允许读取的固定 Markdown/text 目录。
- `obsidianVaults`：只放允许读取的 Obsidian vault。
- `links`：只放明确要进入今日整理的文章或链接摘要。
- `dingtalk`：只放明确的文档 URL、node id、表格范围、日程时间范围。
- `feishu`：只放明确的文档 token、妙记 token、日程/任务开关。
- `outputs`：指定 `wikiContext`、`dailyContext`、`dailyMarkdown` 输出路径。

推荐先用 `mode: "modifiedToday"` 或 `mode: "explicitFiles"`，避免把旧资料全部带入今日总结。普通文章和文档只作为资料，不会自动变成待办；只有明确 action intent 的内容才进入任务候选。

## 4. 有钉钉时

钉钉依赖官方 DingTalk Workspace CLI，命令名 `dws`。可以全局安装，也可以放在项目内 `tools/dws/dws`。

```bash
dws auth status
# 或
./tools/dws/dws auth status
```

如果未登录，先运行：

```bash
dws auth login
```

配置示意：

```json
{
  "dingtalk": {
    "enabled": true,
    "cli": "./tools/dws/dws",
    "documents": [
      { "url": "https://alidocs.dingtalk.com/i/nodes/xxx", "title": "项目文档" }
    ],
    "sheets": [
      { "nodeId": "SHEET_NODE_ID", "range": "A1:Z80", "title": "项目表格" }
    ],
    "calendar": {
      "enabled": true,
      "start": "2026-06-09T00:00:00+08:00",
      "end": "2026-06-10T00:00:00+08:00"
    },
    "todos": { "enabled": true }
  }
}
```

注意：这里的日程是整天时间段，不是只拉待办。拉取失败时脚本会记录错误，不会伪装成已经读取。

## 5. 有飞书时

飞书路径依赖已登录的本地 `lark-cli`。先确认登录状态，再只配置明确 token 或开关：

```bash
lark-cli auth status
```

如果评委环境没有飞书 CLI，就关闭 `feishu.enabled`，改走离线 demo 或本地资料路径。

## 6. 只有本地资料或 Obsidian 时

配置 `localMarkdownDirs` 和 `obsidianVaults`，只允许读取固定区域：

```json
{
  "localMarkdownDirs": [
    {
      "path": "/absolute/path/to/allowed-notes",
      "mode": "modifiedToday",
      "files": []
    }
  ],
  "obsidianVaults": [
    {
      "path": "/absolute/path/to/allowed-vault",
      "mode": "explicitFiles",
      "files": ["Daily/2026-06-09.md"]
    }
  ]
}
```

不要把 home、Downloads、Desktop 根目录、全盘、整个 iCloud Drive 或所有 Obsidian 库作为输入。

## 7. 一键同步固定来源

配置完成后，从仓库根目录执行：

```bash
python scripts/sync_work_memory.py \
  --config work_memory_config.local.json
```

成功后至少会产生：

- `<memoryHome>/sources.jsonl`：已导入来源，按内容 hash 去重。
- `<memoryHome>/import_records.jsonl`：导入状态、来源系统、路径/URL、错误字段和导入时间。
- `out/wiki_context.md`：给本地 Agent 做长期知识沉淀。
- `out/daily_context.md`：给本地 Agent 生成今天总结、今天会议、今天要做什么、今天看的文章。
- `out/daily_memory.md`：同步后生成的今日 memory 草稿。

如果配置了别的 `outputs.*` 路径，以配置为准。

## 8. 本地 AI 工具调用：rerank

同步后可以运行本地 AI rerank 工具：

```bash
python scripts/local_ai_rerank.py \
  --memory-home .aipc-work-memory \
  --query "今天会议 今天要做什么 今天看的文章" \
  --backend token \
  --output out/local_rerank.json
```

真实 AI PC 演示建议改成本地 embedding：

```bash
python scripts/download_ollama_model.py --model qwen3.6-35b-a3b
python scripts/local_ai_rerank.py \
  --memory-home .aipc-work-memory \
  --query "今天会议 今天要做什么 今天看的文章" \
  --backend localhost-embeddings \
  --endpoint http://localhost:11434/v1/embeddings \
  --model LOCAL_EMBED_MODEL \
  --output out/local_rerank.json
```

或 OpenVINO 本地模型目录：

```bash
python scripts/prepare_openvino_embedding.py \
  --model-id BAAI/bge-small-zh-v1.5 \
  --output models/openvino/bge-small-zh-v1.5

python scripts/local_ai_rerank.py \
  --memory-home .aipc-work-memory \
  --query "今天会议 今天要做什么 今天看的文章" \
  --backend openvino \
  --model models/openvino/bge-small-zh-v1.5 \
  --output out/local_rerank.json
```

`localhost-embeddings` 只能连 `localhost` / `127.0.0.1` / `::1`；`openvino` 只能读取本地模型目录。不要在参赛路径里调用远程 embedding 或远程模型 API。

OpenVINO 一键验证：

```bash
python scripts/verify_submission.py \
  --embedding-backend openvino \
  --embedding-model /absolute/path/to/local-openvino-embedding-model
```

详细说明见 `examples/openvino-rerank/README.md`。默认离线验证使用 `token` backend，以保证没有 OpenVINO 环境时也能复现 Skill 链路。

## 9. 本地模型生成最终 DailyResult

脚本负责准备上下文、校验和保存；最终整理内容由本地 Agent 大脑生成。

输入：

- `out/daily_context.md`
- `out/wiki_context.md`
- 可选 `out/local_rerank.json`
- prompt：`examples/agent_prompt.daily_result.md`

输出必须是 `DailyResult` JSON，保存为 `out/daily_result.json`。然后执行：

```bash
python scripts/validate_daily_result.py out/daily_result.json
python scripts/save_daily_result.py \
  --input out/daily_result.json \
  --date 2026-06-09 \
  --markdown-output out/daily_memory.md
```

最终可读 Markdown 今日 memory 在 `out/daily_memory.md`。结构化结果会进入 `<memoryHome>` 下的 daily result 存储。

## 10. 失败状态怎么处理

| 现象 | 处理 |
| --- | --- |
| 没有 `dws` | 走离线 demo、本地资料路径，或先安装 DingTalk Workspace CLI。 |
| `dws auth status` 失败 | 运行 `dws auth login`；仍失败就关闭 `dingtalk.enabled`。 |
| 没有 `lark-cli` | 关闭 `feishu.enabled`，或改用本地导出的 Markdown。 |
| 没网 | 不启用钉钉/飞书实时拉取；`links` 只用已填的 `summary`/`body`；离线 demo 可完整运行。 |
| 没本地模型 | 可以验证脚本链路和 mock；正式提交演示需要本地模型生成 `DailyResult`。 |
| 没 OpenVINO | 用 `token` 做确定性测试，或用本地 `localhost-embeddings`。 |
| 某个私有文档读不到 | 记录错误并跳过，不要编造文档内容。 |

## 11. 关键文档索引

- 包说明：`modelscope-skills/README.md`
- 主 Skill：`SKILL.md`
- 离线 demo：`examples/demo-workday/README.md`
- 本地 Agent prompt：`examples/agent_prompt.daily_result.md`
- 配置样例：`examples/work_memory_config.sample.json`
- OpenVINO 演示：`examples/openvino-rerank/README.md`
- 一键验证脚本：`scripts/verify_submission.py`
- 提交清单：`modelscope-skills/submission-checklist.md`
- 参赛文章草稿：`modelscope-skills/submission-article-draft.md`
