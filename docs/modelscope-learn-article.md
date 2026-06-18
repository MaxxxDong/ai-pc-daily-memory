# AI PC Daily Memory：用本地 Agent 沉淀每日工作记忆

自定义标签：Intel AI PC

## 摘要

AI PC Daily Memory 是一个面向 AI PC Agent Skills 活动的本地优先 Agent Skill。它解决的是一个很具体的工作流问题：每天的信息分散在会议日程、钉钉/飞书文档、本地 Markdown、Obsidian、临时文章和项目笔记里，真正需要的是把这些资料按当天上下文汇总成一份可复用的今日 memory，而不是再做一个泛化聊天助手。

这个 Skill 的设计目标是让 35B 以下本地模型作为 Agent 大脑，调用本地工具完成资料同步、去重、RAG 上下文准备、本地 rerank、结构化结果校验和最终保存。它不依赖云端模型，不扫描全盘，也不默认读取所有云文档；所有来源都必须在配置中明确指定。

## 为什么选择“每日工作记忆”这个场景

AI PC 的优势不是把所有事情都交给云端，而是把用户本地、私有、碎片化的工作上下文组织起来。对个人开发者或创业团队来说，每天真正需要沉淀的内容通常包括：

- 今天有哪些会议和日程；
- 哪些文档、文章、便签和项目记录与今天有关；
- 哪些信息应该沉淀为长期知识；
- 哪些事项需要进入今天的任务列表；
- 哪些来源读取失败，不能被模型编造成已经读取。

传统做法往往是手工复制、人工筛选、再让模型总结。这个过程重复、容易漏信息，也很难验证。AI PC Daily Memory 把这套流程拆成多个本地工具，让 Agent 负责调度，而不是把所有逻辑塞进一次 prompt。

## 实践路径

整个 Skill 的实践路径分为五步。

第一步是显式配置资料来源。配置文件中可以指定本地 Markdown 目录、Obsidian vault、文章链接摘要、钉钉文档、钉钉表格、整天日程、待办、飞书文档、飞书妙记、飞书日程和任务。这里刻意没有做“扫描所有资料”的能力，因为 AI PC 场景里隐私边界比召回率更重要。

第二步是运行本地同步工具。`sync_work_memory.py` 会把配置中的来源导入本地 memory store，生成 `sources.jsonl` 和 `import_records.jsonl`。内容按 hash 去重，来源读取失败会记录错误，不会伪装成成功。

第三步是准备上下文。Skill 会分别生成面向当天总结的 `daily_context.md` 和面向长期沉淀的 `wiki_context.md`。这样本地模型不需要直接面对所有原始文件，而是读取经过整理和筛选的上下文。

第四步是调用本地 AI 工具。默认离线验证使用确定性的 token rerank；如果评委或用户有本地 embedding 模型，可以切换到 localhost embeddings 或 OpenVINO 本地模型目录。OpenVINO 路径使用 `local_files_only=True`，不会在评审路径中下载远程模型。

第五步是由本地小模型生成 `DailyResult`，再通过 `validate_daily_result.py` 校验结构，最后由 `save_daily_result.py` 保存成 Markdown 今日 memory。这个设计把“生成内容”和“保存结果”分开，减少模型输出格式不稳定带来的风险。

## Skill 架构

这个 Skill 不是单个脚本，而是一个可由 Agent 调用的本地工具链：

- `sync_work_memory.py`：统一同步配置中的本地、钉钉、飞书和链接来源；
- `prepare_daily_context.py`：生成今天总结所需上下文；
- `prepare_wiki_context.py`：生成长期知识沉淀上下文；
- `local_ai_rerank.py`：调用本地 token、localhost embedding 或 OpenVINO backend 做 rerank；
- `validate_daily_result.py`：校验本地模型输出的结构化结果；
- `save_daily_result.py`：保存最终今日 memory；
- `verify_submission.py`：给评委提供无网、无钉钉、无飞书环境下的离线完整验证路径。

在无网环境中，评委可以直接运行：

```bash
python3 scripts/verify_submission.py
```

这个命令会在临时目录中跑完整链路，验证资料同步、上下文生成、本地 rerank、mock DailyResult、结构校验和最终 Markdown 保存。

## 本地 AI 工具与 OpenVINO

赛事要求强调“用 35B 以下小模型作为 Agent 大脑，驱动本地 AI 工具调用”。在这个作品里，本地模型负责理解上下文并生成结果，本地工具负责把资料准备好、排序好、验证好。

OpenVINO 在这里扮演的是本地 embedding/rerank 工具角色。它不是强行替代 Agent 大脑，而是作为 Agent 可以调用的本地 AI 工具，用于提升上下文排序质量。这样设计有两个好处：

第一，默认验证路径仍然可复现。没有 OpenVINO 环境时，`token` backend 可以保证功能链路稳定通过。

第二，有 AI PC 硬件和本地模型时，可以切换到 OpenVINO backend，让 NPU/GPU 参与本地语义检索和 rerank，体现 AI PC 的硬件价值。

示例命令：

```bash
python scripts/local_ai_rerank.py \
  --memory-home .aipc-work-memory \
  --query "今天会议 今天要做什么 今天看的文章" \
  --backend openvino \
  --model /absolute/path/to/openvino-embedding-model \
  --output out/local_rerank.json
```

## Hybrid AI 的思考

我对 Hybrid AI 的理解不是“本地和云端都用一点”，而是按数据敏感度、推理成本和时延要求重新划分边界。

在每日工作记忆这个场景里，会议、项目笔记、私人文档和本地知识库更适合留在本地。它们不一定需要最强的云端模型，反而更需要稳定、私密、可重复调用的本地工具链。AI PC 上的本地小模型负责理解和组织这些上下文，本地 embedding/OpenVINO 工具负责检索和排序，本地文件系统负责保存结果。

云端仍然有价值，但更适合放在非隐私、高吞吐或协作发布环节。例如公开技术文章、开源仓库、比赛提交页面、团队协作系统等。也就是说，Hybrid AI 的关键不是简单混用，而是让私有上下文在本地闭环，让公开协作和分发走云端。

AI PC Daily Memory 的设计选择是：评审路径不依赖云端模型；真实办公路径可以接入钉钉和飞书 CLI，但读取范围必须显式配置；生成和保存结果都由本地 Agent 与本地脚本完成。这种边界更符合 AI PC 的定位。

## 优化心得

第一个优化点是把失败显式化。真实资料来源经常会因为登录、权限、网络或 CLI 不可用而失败。这个 Skill 不会把失败来源当作空内容默默跳过，而是写入 `import_records.jsonl`，让 Agent 能知道哪些来源没有成功读取。

第二个优化点是避免过度召回。很多 RAG 系统的问题不是资料太少，而是把不相关资料也塞进上下文。这里通过显式目录、日期过滤、内容 hash 去重和本地 rerank，把上下文规模控制在当天任务能消费的范围内。

第三个优化点是把结构校验放在模型输出之后。`DailyResult` 不是自由文本，而是包含会议、任务、阅读、沉淀知识和错误状态的结构化 JSON。模型先生成 JSON，再由脚本校验，再保存 Markdown。这样可以降低 Agent Skill 在不同本地模型下的输出波动。

第四个优化点是离线 demo 和真实路径分离。评委可以无网运行 `verify_submission.py` 验证核心能力；真实用户可以配置钉钉、飞书、Obsidian 和本地目录跑完整工作流。这样既保证可评审，也保留真实使用价值。

## 安全边界

这个 Skill 明确限制了几个行为：

- 不扫描全盘；
- 不默认读取用户 home、Downloads、Desktop 根目录；
- 不自动读取所有云文档；
- 不在评审路径调用远程 embedding 或远程模型 API；
- 不在读取失败时编造内容；
- 不把普通文章自动变成待办，只有明确 action intent 的内容才进入任务候选。

这些限制看起来会降低“自动化程度”，但对个人工作记忆类应用来说，这是必要的产品边界。

## 复现方式

克隆仓库后，可以先跑离线验证：

```bash
python3 scripts/verify_submission.py
```

也可以安装 pytest 后跑测试：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip pytest
python -m pytest tests -q
```

真实使用时，先复制示例配置：

```bash
cp examples/work_memory_config.sample.json work_memory_config.local.json
```

然后只填入允许读取的目录、vault、文档 URL、日程范围和输出目录，再运行：

```bash
python scripts/sync_work_memory.py --config work_memory_config.local.json
```

最终输出包括 `daily_context.md`、`wiki_context.md`、`daily_memory.md` 和导入记录。Agent 读取上下文后生成 `DailyResult`，再由保存脚本写回本地今日 memory。

## 总结

AI PC Daily Memory 的核心不是做一个更大的个人知识库，而是把每天真实发生的工作上下文整理成可保存、可验证、可继续使用的 memory。它把本地小模型、本地工具调用、本地文件系统、OpenVINO rerank 和显式资料边界组合起来，形成一个更适合 AI PC 的 Hybrid AI 工作流。

在我看来，AI PC Agent Skill 的价值不只在于“模型能调用工具”，更在于工具链能否承载真实场景里的边界、失败和复现。这个作品尝试把这些问题放进一个小而完整的每日工作流里。
