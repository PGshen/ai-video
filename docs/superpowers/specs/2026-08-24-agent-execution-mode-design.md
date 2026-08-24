# Agent 执行模式设计

日期：2026-08-24

## 背景与问题

叙事生成和代码生成目前采用「一次请求 LLM → 本地检查 → 有问题就重新请求」的模式：

- `NarrativeWorker` 调 `provider.generate_narrative()` 拿到整包 scenes JSON，无校验重试。
- `CodeWorker` 调 `provider.generate_code()` 拿到 N 段代码，合并进 scenes，然后跑
  `ManimEngine.validate_code()`，失败则调 `provider.repair_code()`，最多 2 轮，仍失败即抛错。

失败率偏高，效果不稳定。根因有三点：

1. **每轮 repair 都是全新的 LLM 调用**。模型看不到自己上一轮改了什么、为什么改，
   每次都要从「整包代码 + 一段报错」重新理解现场。
2. **产物是一个巨型 JSON**。`codes` 数组里任何一段有问题，整个响应作废；模型也无法
   只重写出问题的那一段。
3. **反馈信号被压平**。`validate_code()` 已经把 traceback 定位到了具体的 `_scene_N`
   （`app/engines/render/manim.py`），这个精确信息被拼进一个大 prompt 交给模型，
   而不是作为一次可行动的工具返回值。

## 目标

新增一种「Agent 迭代」执行模式，底层用 Claude Agent SDK，让模型在**同一个会话上下文里**
反复「写文件 → 跑校验 → 读报错 → 改文件」直到通过。现有的提示词模式完整保留，
在平台上可配置选择使用哪种。

### 非目标

- 不改渲染、TTS、审核闸门等其它环节。
- 不重构 `BaseWorker` 的取消语义（见「取消」一节）。
- 不做真实 Agent 的端到端自动化测试。

## 架构：执行策略层

被替换的单元是**整个迭代过程**，而不是「一次 LLM 调用」——Agent 模式要取代的正是
`CodeWorker._execute` 里那段「生成 → validate → repair×2」的循环。因此策略边界切在
worker 与生成逻辑之间，而不是切在 `AIProvider` 上。

新增 `app/services/strategies/`，内含两组同构的策略：

- 代码侧：`PromptCodegenStrategy`（现有逻辑原样搬入，行为不变）、`AgentCodegenStrategy`。
- 叙事侧：`PromptNarrativeStrategy`、`AgentNarrativeStrategy`。

两者签名相同：输入 `scenes + style_components + render_engine + aspect_ratio`，
输出 `merged_scenes + 执行轨迹`。`CodeWorker._execute` 瘦身为：取 payload → 选策略 →
调用 → 落库。

这顺带解决一个已有问题：`code_worker.py` 的 `_execute` 把「取数据 / 生成 / 校验修复 /
落库」四件事塞在一个函数里。抽策略正好把它拆开。

## Agent 契约与沙箱协议

### 沙箱布局

每次执行开一个 `tempfile.TemporaryDirectory()` 作为 `cwd`，平台预先写入：

```
input.json    镜头叙事（scene_index / narration / description / beats / duration_seconds）
STYLE.md      style_components 三件套 + aspect_ratio + 引擎约束（由 prompt_bundle 拼出）
scenes/       Agent 在此写 scene_00.py … scene_NN.py，一个镜头一个文件
```

一镜头一文件是 Agent 模式相对提示词模式的核心结构性收益：Agent 可以只重写出错的那个
文件，且每次修改是 `Edit` 粒度而非全量重写。

### 工具面

- `tools=["Read", "Write", "Edit", "Glob"]` —— 用 `tools` 白名单把 Bash / WebSearch /
  WebFetch 从 Claude 的上下文中**移除**（availability 层），而非用 `disallowed_tools`
  事后拒绝。worker 容器持有数据库和 MinIO 凭证，不给 Bash 是硬要求。
- `mcp__codegen__validate` —— in-process MCP 工具（`@tool` + `create_sdk_mcp_server`），
  包住 `ManimEngine.validate_code()`。handler 读 `scenes/` 下当前全部文件、拼 `SceneInput`
  列表、调 `validate_code`，把 `(is_valid, errors)` 转为 `content` 文本返回，
  失败时带 `is_error: True`。

`validate_code()` 报错中已有的「traceback 定位到 `_scene_N`」加工，在 Agent 模式下
直接成为「该改哪个文件」的行动指引。

### Agent 选项

- `setting_sources=[]` —— 必须显式清空，否则 SDK 会读取容器内 `~/.claude` 及项目级
  settings，使生产行为依赖宿主机残留配置。
- `permission_mode="acceptEdits"`，`cwd` 限定在 tmpdir。
- `max_turns=40` 作为死循环兜底。
- `env={"ANTHROPIC_API_KEY": ...}`，`base_url` 非空时追加 `"ANTHROPIC_BASE_URL"`；
  为空则不传该键，走官方端点。
- 用 `query()` 单次调用；不需要 `ClaudeSDKClient`（一次任务一个会话，不做多轮追问）。
- 默认模型 `claude-opus-5`，可在 provider 配置中覆盖。

### 结束判据

`query()` 是一整个 agent 会话：写文件 → 调 `validate` → 读报错 → `Edit` → 再校验，
全部在这一次调用的迭代中完成，`ResultMessage` 到达时循环结束。

但循环结束有三种可能，只有第一种是真通过：

1. Agent 确认校验通过，正常结束；
2. Agent 卡住，自述「改不动了 / 剩下的问题不影响」后结束回合——**它以为完成了，其实没过**；
3. 撞到 `max_turns` 被截断。

SDK 没有「必须校验通过才准停」的强制机制。因此：**平台不信任 Agent 的自述**。
`query()` 返回后，策略层自行从 `scenes/` 回读文件、再跑一次 `validate_code`，
通过才算成功。这是唯一可信的判据。

## 数据模型与配置

### Anthropic 接入

复用现有 provider 表，不新开一套：

- `AI_PROVIDER_TYPES` 增加 `"anthropic"`。
- 在 `ai_model_providers` 建普通记录：`api_key` 填 key，`base_url` 留**空串**表示走官方
  端点、填值表示走中转。工厂里判空即可。用空串而非放宽 `base_url` 为 nullable，
  是为了不动其它 provider 的读路径。
- 模型行照常建在 `ai_provider_models`（`model = "claude-opus-5"`，带定价）。

`content_max_tokens` / `json_max_tokens` 对 Agent 模式无意义（SDK 自管上下文与输出长度），
不传。接受这两列在 Agent 行上冗余，不为此给设置页开分支。

### 执行模式：两层，任务创建时冻结

- **全局默认**：`ai_business_model_configs` 增加 `execution_mode` 列
  （`'prompt'` / `'agent'`，默认 `'prompt'`）。这张表本就是「某业务环节用哪个模型」，
  「用哪种执行方式」是同一件事的另一半。
- **项目级**：`video_projects` 增加 `execution_mode` 列，**可空**，`NULL` 表示继承全局。
  空值语义优于给定默认值：将来改全局默认，老项目会跟随，而非被创建时的快照钉死。
- **解析时机**：在 `activities.py` 派发任务时解析（项目级 → 全局 → 默认），
  结果写入 `input_payload["execution_mode"]`。Worker 不查库、不做决策。

这与现有 `prompt_snapshot` 同一原则：`activities.py` 已在派发时快照风格组件，
使「任务入队那一刻的配置」不受后续改动影响。一个跑了 20 分钟的 Agent 任务，
中途有人在设置页切了模式，不应影响它。

### 产物溯源

`narrative_versions` / `code_versions` 已有 `prompt_snapshot` (JSONB) 和 `ai_model` 列，
不加新列：

- `ai_model` 写实际模型（`claude-opus-5`）。
- `prompt_snapshot` 增加 `execution_mode`，以及 `agent` 子对象：SDK 版本、`max_turns`、
  实际轮次、`total_cost_usd`、平台侧最终校验是否一次通过。

审核页面回看版本时可直接看出「这版是 Agent 跑的、迭代 7 轮、花了 $0.34」。

### 不入库的配置

`max_turns`、单次预算上限、Agent 超时放 `settings`（env）。这些是运维旋钮而非业务配置，
不做成表和 UI。

### 迁移

一个 alembic revision：`ai_business_model_configs.execution_mode`、
`video_projects.execution_mode` 两处 `add_column`，加上 `AI_PROVIDER_TYPES` 常量修改。
纯加列，均有默认值或可空，不动存量数据。

## 可观测性

### 成本记录

现有成本审计挂在 `RecordingChatClient` 上，包住每次 HTTP 请求。Agent 模式下这层拦不住
——请求由 SDK 内部发出。

改为在策略层记一条，**一次 Agent 执行 = 一条 `ai_call_records`**，`request_type = "agent"`：

- `input`：沙箱输入摘要（镜头数、风格组件 sha、模型、max_turns）
- `output`：`ResultMessage.result`
- 成本：直接取 `ResultMessage.total_cost_usd`，SDK 已累加整个会话所有轮次。
  不复算，也不使用 `ai_provider_models` 上的 per-million 定价（那是给 chat 模式用的）。

### 执行轨迹

迭代 `query()` 消息流时收集 `ToolUseBlock`，形成精简 trace（轮次、工具名、`validate`
通过与否、报错首行），随 `worker_tasks.output_payload` 落库。完整消息流走 `logger`，
不入库——Agent 中间文本很长，入 JSONB 只会让该表变重。

## 失败处理

三层，一层比一层粗：

1. **Agent 内部**：`validate` 报错即反馈信号，自行迭代。主路径。
2. **平台回读校验不过**：用 `resume` 拉回同一会话，附上平台侧 `errors` 继续修，
   **只给一次**。给一次而非多次的理由：Agent 已认为收敛而平台判定未过，说明它对失败的
   理解出现偏差；同一上下文中再多轮通常重复同样的判断，烧钱不解决问题。
3. **仍不过**：`raise`，交给 `BaseWorker` 现有 `max_retries` 整体重跑（新沙箱、新会话）。
   换个起点比在坏上下文里挣扎更可能成功。

### 成本刹车

`max_turns` 是确定可用的硬上限。`ClaudeAgentOptions` 疑似还有 `max_budget_usd`，
但官方文档中仅见一处顺带提及，未见明确字段定义。**实现时先按 `max_turns` 做上限**，
在落地顺序第 3 步实地验证 SDK 是否支持该字段：支持则加上，不支持则在每轮累计成本
超阈值时主动 break。不在设计中假定其存在。

## 取消

`BaseWorker._process_task` 只在 `_execute` **返回之后**才检查取消状态——任务跑完才发现
已被取消，然后丢弃结果。提示词模式下一次调用几十秒，无所谓；Agent 模式一跑十几分钟
还在烧钱，用户点了取消却毫无反应，不可接受。

策略层在迭代 `query()` 消息流时顺带检查任务状态，已取消则 break 出循环、清理沙箱、
抛取消异常。

不重构 `BaseWorker` 的取消语义使所有 worker 支持中途取消——那会影响渲染等其它路径，
超出本次范围。就在策略层解决，够用且不外溢。

## 不变的部分

叙事 Agent 产出 scenes 后，TTS 合成、beats 对齐、落库全部走现有路径
（`narrative_worker.py` 中 `_synthesize_scenes_tts` 起）。Agent 只替换
「怎么把 scenes 生出来」这一段。

## 测试策略

Agent 循环本身无法在 CI 中运行（慢、贵、不确定）。关键是把接缝切对：策略注入一个
`agent_query` 可调用对象，默认为 SDK 的 `query`，测试传入假实现。

**1. MCP 工具处理函数**（纯函数）
`validate` handler 不需要任何 Agent 即可测试：在 tmpdir 放入已知好/坏的 scene 文件，
断言返回的 `is_error` 与文本中是否带上镜头编号。复用 `tests/test_manim_render_engine.py`
已有的好坏代码样本。

**2. 策略编排逻辑**（假消息流）
假 `agent_query` 吐出预设消息序列，断言：

- Agent 声称成功但 `scenes/` 中代码实际不过 → 平台判失败并触发 `resume`；
- `resume` 后仍不过 → 抛错，且**只 resume 一次**；
- `ResultMessage.subtype != "success"` → 判失败；
- 迭代途中任务被标记 cancelled → break、清沙箱、抛取消异常；
- 成本与轮次正确写入 `prompt_snapshot` 与 `ai_call_records`。

其中第一条最关键——「不信任 Agent 自述」是整个设计的安全底座，必须有测试钉死，
否则日后有人图省事删掉回读校验，无人会发现。

**3. 模式路由**
`activities.py` 按 项目级 → 全局 → 默认 解析并写入 payload；worker 按 payload 选策略。
扩展 `test_activities.py` 与 `test_code_worker.py`。

**明确不做**：真实 Agent 端到端自动化测试。靠手工验证（`make up` 环境跑真实选题，
看 Temporal UI 与 trace）。不写需要 API key 才能跑的测试，那会让 CI 变成
「大部分时候被 skip 的绿色」。

**回归保护**：`PromptCodegenStrategy` 是原样搬运，不改行为。`test_code_worker.py` /
`test_narrative_worker.py` 的现有断言应当**一行不改地继续通过**——若需要改，
说明搬运时改了行为，那是 bug 不是重构。这是本次重构的验收线。

## 落地顺序

每步独立可验证，前一步不通过不进下一步。

1. **抽策略层，不加新功能** —— 现有逻辑搬进 `PromptCodegenStrategy` /
   `PromptNarrativeStrategy`，worker 瘦身。现有测试必须全绿。单独成一个 commit。
2. **数据模型与配置** —— 迁移、`AI_PROVIDER_TYPES` 加 `anthropic`、`activities.py`
   解析模式写入 payload。此时全局默认仍为 `prompt`，行为无变化。
3. **镜像与依赖** —— `backend/Dockerfile` 装 `@anthropic-ai/claude-code`（Node 22 已有，
   为 Remotion 装过）、`pyproject.toml` 加 `claude-agent-sdk`。
   **在此步实地确认 `ClaudeAgentOptions` 是否有 `max_budget_usd`**，结掉该不确定项。
4. **代码侧 Agent 策略** —— MCP 工具 + 策略 + 测试。先只做代码侧：它失败率最高、
   闭环信号最硬，是验证整套架构的最佳试验田。
5. **手工端到端验证代码侧** —— 真跑一个项目。通过后再往下。
6. **叙事侧 Agent 策略** —— 结构校验工具（包住 `validate_scenes_for_codegen` +
   schema 校验：beats 完整性、scene_index 连续、字段缺失、旁白长度）+ 分阶段草稿
   （先写大纲文件，再展开逐镜头旁白），复用第 4 步验证过的骨架。
7. **前端** —— 项目创建/设置页的模式选择；审核页显示「Agent 跑的，N 轮 / $X」。

第 6 步的收益不如代码侧确定（叙事没有 manim 那样的硬校验信号）。若第 5 步结果显示
Agent 模式提升有限，第 6 步应重新评估而非照单硬做——届时以代码侧实测数据为准再决定。
