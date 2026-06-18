# ModelScope AIPC Skill 提交清单

## 必交内容

| 项目 | 当前材料 | 提交动作 |
| --- | --- | --- |
| Skill 作品包 | GitHub 仓库根目录 | 在 ModelScope Skills Center 选择“从 Github 仓库快速创建”，导入当前公开仓库；根目录只能有一个 `SKILL.md`，但 README/docs/scripts/examples/tests/model.json/requirements 都应一并勾选。 |
| 代码 | `scripts/`、`tests/`、`examples/` | 随主 Skill 一起提交；如果平台支持 sibling skills，再补交 3 个子 Skill 目录。 |
| 文档 | `README.md`、`AGENT_RUNBOOK.md`、`examples/demo-workday/README.md` | 主入口写 `AGENT_RUNBOOK.md`，评委先跑 `scripts/verify_submission.py`。 |
| 测试用例 | `tests/`、`scripts/verify_submission.py` | 本地运行 `python scripts/verify_submission.py` 和 `python -m pytest tests -q`。 |
| 技术文章 | `docs/modelscope-learn-article.md` | 已发布到 `https://www.modelscope.cn/learn/434338`，提交表必须填写这个 URL，不要填写文章标题。 |
| 模型准备脚本 | `scripts/download_ollama_model.py`、`scripts/prepare_openvino_embedding.py` | 提供 Ollama 模型拉取/校验和 OpenVINO embedding 下载转换命令。 |

## 发布步骤

1. 在主 Skill 目录运行验证：

```bash
python scripts/verify_submission.py
```

2. 从仓库根目录生成干净提交包，只包含 Git 已跟踪文件，不会混入 `out/`、`.aipc-work-memory/`、本地 dws 或私有配置：

```bash
git archive --format=zip \
  -o ai-pc-daily-memory-submission.zip \
  HEAD
```

3. 可选：准备本地模型。Ollama Agent 大脑：

```bash
python scripts/download_ollama_model.py --model qwen3.6-35b-a3b
```

如果赛事基准模型在 Ollama registry 中名称不同，改用实际模型名并同步设置 `AIPC_LLM_MODEL`。

4. 可选：准备 OpenVINO embedding 模型目录：

```bash
python -m pip install -r requirements-openvino.txt
python scripts/prepare_openvino_embedding.py \
  --model-id BAAI/bge-small-zh-v1.5 \
  --output models/openvino/bge-small-zh-v1.5
```

5. 可选：如果本机已有 OpenVINO embedding 模型目录，运行：

```bash
python scripts/verify_submission.py \
  --embedding-backend openvino \
  --embedding-model models/openvino/bge-small-zh-v1.5
```

6. 打开 `https://www.modelscope.cn/skills`，点击“新建 skill”，选择“从 Github 仓库快速创建”，填写 `https://github.com/MaxxxDong/ai-pc-daily-memory`。
7. 在文件选择步骤勾选全部项目文件。根目录必须只有一个 `SKILL.md`，但 README、`AGENT_RUNBOOK.md`、docs、scripts、examples、tests、`model.json`、requirements 文件都要导入。
8. Skill 标签至少包含 `AIPC`；描述中明确写：本地 `<=35B` Agent 大脑、localhost、本地 OpenVINO/embedding rerank、私有工作记忆。
9. 打开 `https://www.modelscope.cn/learn`，点击“创建文章”，粘贴 `docs/modelscope-learn-article.md`，添加 `Intel AI PC` 标签。
10. 活动提交表的研习社文章链接填写 `https://www.modelscope.cn/learn/434338`；Skill 链接填写 GitHub 导入版 `https://modelscope.cn/skills/dwj0725/ai-pc-daily-memory-aipc`。

## 建议截图

| 截图 | 目的 |
| --- | --- |
| `verify_submission.py` 终端输出 | 证明评委一条命令可复现。 |
| `out/daily_context.md` | 证明资料已进入本地 RAG 上下文。 |
| `out/local_rerank.json` 或 OpenVINO rerank 输出 | 证明 Agent 调用了本地 AI 工具。 |
| `out/final_daily_memory.md` | 证明最终今日 memory 可读、可保存。 |
| 钉钉 `dws auth status` 和整天日程导入结果 | 证明真实线上资料适配能力。没有评委登录态时放为增强截图，不作为默认验收路径。 |

## 评分映射

| 评分项 | 材料 |
| --- | --- |
| Skill 可用性 30% | `verify_submission.py`、pytest、离线 demo、错误处理、固定来源配置。 |
| 场景价值 20% | 今日总结、会议、文章、任务和长期知识沉淀，覆盖真实个人工作流。 |
| 技术深度 20% | Skill-owned memory store、hash 去重、RAG 上下文、本地 rerank、localhost/OpenVINO backend、schema 校验。 |
| 文章质量 15% | 复现命令、架构图、评分映射、失败状态说明、截图。 |
| 创新性 15% | 从分散资料到“今日工作记忆”的本地 Agentic 工作流，不是单次总结 prompt。 |

## 小红书文案草稿

标题：

AI PC 上的私人工作记忆 Skill：本地 Agent 自动整理今天的会议、资料和待办

正文：

我做了一个面向 ModelScope AI PC Agent Skills 的本地工作记忆 Skill。它不依赖云端模型，也不扫描全盘，只读取用户明确配置的 Markdown、Obsidian、钉钉/飞书资料和链接摘要。本地 `<=35B` Agent 大脑会调用 Skill 脚本生成 RAG 上下文，再用本地模型生成今日总结、会议列表、待办、文章沉淀和可保存的 daily memory。

技术点：

- 本地 memory store + hash 去重
- 固定来源同步，不读未授权资料
- localhost / OpenVINO embedding rerank
- DailyResult JSON schema 校验
- 一条命令可跑离线 demo

配图建议：

1. 流程图：资料来源 -> 本地记忆库 -> rerank/RAG -> 本地模型 -> 今日 memory
2. `verify_submission.py` 运行截图
3. `daily_context.md` 与 `final_daily_memory.md` 对比
4. OpenVINO rerank 输出

发布时带话题：

`#英特尔 #openvino #魔搭社区 #modelscope #agentic #skills`

并按活动要求 @OpenVINO中文社区 和 @魔搭ModelScope社区。
