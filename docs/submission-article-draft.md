# AI PC Daily Memory：用本地 Agent 管理每日工作记忆

> 建议标签：`Intel AI PC`

## 1. 为什么做这个 Skill

真实工作里的信息不是只存在一个聊天窗口里。会议在日历里，资料在钉钉/飞书里，灵感在 Obsidian 或 Markdown 里，今天看的文章又散在链接和摘录里。普通对话式 AI 很难持续追踪这些资料，也容易把普通文章误判成待办。

AI PC 的价值在于：用户的隐私资料可以留在本机，由本地 `<=35B` Agent 大脑调用本地工具完成整理。这个 Skill 的目标就是把“今天发生了什么、今天要做什么、今天看了什么、哪些知识值得沉淀”变成一个可复用的本地 Agentic 工作流。

## 2. 作品简介

`AI PC Daily Memory` 是一个 local-first Agent Skill。它不依赖桌面便签 App，也不依赖 Codex CLI。评委可以使用 Ollama + Qwen3.6-35B-A3B + QwenPaw/Trae 作为 Agent 大脑，调用 Skill 中的脚本完成：

- 显式来源同步：Markdown、Obsidian、钉钉、飞书、链接摘要。
- 本地工作记忆：写入 `.aipc-work-memory/sources.jsonl`，按内容 hash 去重。
- RAG 上下文准备：生成 `out/daily_context.md` 和 `out/wiki_context.md`。
- 本地 AI 工具调用：用 `local_ai_rerank.py` 做 token / localhost embedding / OpenVINO rerank。
- 结构化输出：本地 Agent 生成 `DailyResult` JSON，脚本校验并保存为 `daily_memory.md`。

## 3. 工作流

```text
固定来源配置
  ├─ Markdown / Obsidian
  ├─ DingTalk dws：文档、表格、整天日程、待办
  ├─ Feishu lark-cli：文档、妙记、日程、任务
  └─ 明确配置的链接摘要
        ↓
sync_work_memory.py
        ↓
.aipc-work-memory/sources.jsonl + import_records.jsonl
        ↓
prepare_wiki_context.py + prepare_daily_context.py
        ↓
local_ai_rerank.py（token / localhost-embeddings / openvino）
        ↓
本地 <=35B Agent 大脑生成 DailyResult
        ↓
validate_daily_result.py + save_daily_result.py
        ↓
out/final_daily_memory.md
```

## 4. 本地 AI 工具调用

这个 Skill 不是只把资料拼成 prompt。它提供了一个可被 Agent 调用的本地 AI 工具：`local_ai_rerank.py`。

三种 backend：

| Backend | 用途 | 本地性 |
| --- | --- | --- |
| `token` | 无模型环境下的确定性验收 | 纯 Python、本地运行 |
| `localhost-embeddings` | 调用本机 OpenAI-compatible embedding 服务 | endpoint 只允许 `localhost / 127.0.0.1 / ::1` |
| `openvino` | 调用本地 OpenVINO embedding 模型目录 | `local_files_only=True`，不下载云端模型 |

OpenVINO 路径示例：

```bash
python scripts/verify_submission.py \
  --embedding-backend openvino \
  --embedding-model /absolute/path/to/local-openvino-embedding-model
```

如果没有 OpenVINO 环境，也可以先跑默认 verification，确认完整链路可用：

```bash
python scripts/verify_submission.py
```

## 5. 复现方式

最短路径不需要钉钉、飞书、网络或云端模型：

```bash
python scripts/verify_submission.py
```

这个命令会在临时目录中完成：

1. 复制 `examples/demo-workday/`。
2. 运行 `sync_work_memory.py`，同步本地 Markdown、Obsidian 和明确链接摘要。
3. 运行 `local_ai_rerank.py`，生成本地 rerank 结果。
4. 用 mock Agent 生成可验证的 `DailyResult`。
5. 运行 `validate_daily_result.py` 校验 JSON schema。
6. 运行 `save_daily_result.py` 保存最终 `final_daily_memory.md`。

输出示例包括：

- `out/daily_context.md`
- `out/wiki_context.md`
- `out/local_rerank.json`
- `out/mock_daily_result.json`
- `out/final_daily_memory.md`

## 6. 真实钉钉路径

默认 demo 不依赖钉钉登录态，但真实工作流可以接入 DingTalk Workspace CLI：

```bash
dws auth login
dws auth status
```

配置中只填写明确授权的文档、表格、日程时间段和待办开关。日程使用整天窗口，例如：

```json
{
  "dingtalk": {
    "enabled": true,
    "cli": "./tools/dws/dws",
    "calendar": {
      "enabled": true,
      "start": "2026-06-09T00:00:00+08:00",
      "end": "2026-06-10T00:00:00+08:00"
    }
  }
}
```

读取失败会在导入记录中体现，不会伪装成已经读取。

## 7. 安全边界

- 不扫描 `/`、用户 home、全盘目录、所有云文档或所有知识库。
- 本地目录必须显式配置，支持 `all`、`modifiedToday`、`explicitFiles`。
- 钉钉/飞书读取失败时明确报错，不编造私有文档内容。
- 普通文章和文档只作为资料，只有明确行动意图才会进入任务候选。
- 参赛路径不调用远程 embedding 或远程模型 API。

## 8. 评分映射

| 评分项 | 对应实现 |
| --- | --- |
| Skill 可用性 30% | `verify_submission.py` 一条命令验证；pytest 覆盖同步、schema、rerank、保存；失败状态显式报错。 |
| 场景价值 20% | 解决个人工作信息分散问题，输出今日会议、待办、文章、知识沉淀和 daily memory。 |
| 技术深度 20% | Skill-owned memory store、hash 去重、本地 RAG、localhost/OpenVINO rerank、DailyResult schema。 |
| 文章质量 15% | 提供复现命令、架构图、输出路径、OpenVINO 路径、失败状态。 |
| 创新性 15% | 把 AI PC 从一次性聊天变成本地工作记忆系统，覆盖多来源同步和可保存结果。 |

## 9. 建议配图

1. `verify_submission.py` 终端输出，重点展示 `ok: true`。
2. `out/daily_context.md`，展示本地资料进入 RAG 上下文。
3. `out/local_rerank.json` 或 OpenVINO rerank 输出，展示本地 AI 工具调用。
4. `out/final_daily_memory.md`，展示最终今日工作记忆。
5. 如果有真实钉钉环境，补一张整天日程导入截图。

## 10. 结论

AI PC Daily Memory 的核心不是做一个更长的总结 prompt，而是把用户明确授权的资料同步、检索、重排、结构化和保存变成一个可复用 Agent Skill。它适合个人研发、产品会议、投资跟进、知识管理等每天都要处理分散资料的场景，也符合 AI PC 对本地性、隐私和低延迟的要求。
