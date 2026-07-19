# 工作流与提示词说明

> 本文档基于当前源码（`backend/app/workflows/`、`backend/app/engines/ai/`、`backend/app/api/reviews.py` 等）梳理，是对 `docs/PRD_产品需求文档.md` 与 `docs/TECH_技术实现方案.md` 的补充和纠偏——两份早期文档在"叙事/代码两阶段拆分""三道审核闸门""语义节拍(beat)时间线""Prompt 快照/风格组件体系"等后续演进的机制上要么缺失要么是简化版伪代码，本文以代码为准。

## 1. 整体状态机

```
draft
 → narrative_generating → narrative_review
 → code_generating       → code_review
 → video_generating       → video_review
 → published
```

失败/终止分支：`narrative_failed`（重试超限，需人工 reset）、`code_failed`（同上，但 workflow 保持存活）、`abandoned`（人工放弃，终态）。

工作流定义：`backend/app/workflows/video_production.py`（`VideoProductionWorkflow`），配套 activities 在 `backend/app/workflows/activities.py`。**权威状态来源是 Temporal workflow 内的状态变量**，`video_projects.status` 只是镜像（写入动作由 `update_project_status` activity 完成，同时追加一条不可变的 `ProjectEvent(event_type="status_change")`）。

### 1.1 各阶段流转细节

| 当前状态 | 触发 | 去向 |
|---|---|---|
| `narrative_generating` | 生成成功 | → `narrative_review` |
| | 生成失败，可重试（`retry_count < 2`） | 重新提交生成任务 |
| | 生成失败，超过重试上限 | → `narrative_failed`（workflow 终止，需人工调用 reset 接口） |
| `narrative_review` | 审核 `approved` | → `code_generating` |
| | 审核 `rejected` | → `narrative_generating`（重新生成） |
| | 审核 `abandoned` | → `abandoned` |
| `code_generating` | 生成成功 | → `code_review` |
| | 生成失败，可重试 | 重新提交 |
| | 生成失败，超过上限 | → `code_failed`（等待人工 reset，workflow 不终止） |
| `code_review` | `approved` | → `video_generating` |
| | `rejected`，`target_stage=code` | → `code_generating` |
| | `rejected`，`target_stage=narrative`（默认） | → `narrative_generating` |
| | `abandoned` | → `abandoned` |
| `video_generating` | 渲染成功 | → `video_review` |
| | 渲染失败（不自动重试） | 自动流转到 `code_review`（`trigger=video_failed`），等待人工在代码审核页处理：`approved`→ 重新提交渲染（`retry_video`）；`rejected`→ 按 `target_stage` 回 `code_generating`/`narrative_generating`；`abandoned`→ 结束 |
| `video_review` | `approved` | → `published`（终态） |
| | `rejected`，`target_stage=narrative` | 状态回到 `narrative_review`（**复用已有叙事版本**，不重新生成，等待人工编辑/重审后进入 `code_generating`） |
| | `rejected`，`target_stage=code`（默认） | 状态回到 `code_review`（**复用已有代码版本**，approved 后直接 `retry_video` 重新渲染，不重新生成代码） |
| | `abandoned` | → `abandoned` |

驳回类型 → 建议回退阶段（`rejection_type` → `target_stage`，产品设计意图）：

| rejection_type | 去向 |
|---|---|
| `topic_invalid` | `abandoned` |
| `fact_error` / `narrative_weak` | 回 narrative 阶段 |
| `code_issue` | 回 code 阶段 |
| `sync_issue`（音画不同步） | 先回 code 阶段 |

### 1.2 Signal 一览

工作流不使用 Temporal Activity 的返回值来感知外部完成状态，而是统一通过 **Signal** 驱动——无论是"机器任务完成"还是"人工审核完成"，都是一次 signal：

| Signal | 发送方 | Payload |
|---|---|---|
| `narrative_generated` | NarrativeWorker | `{success, error?}` |
| `narrative_review` | 审核 API | `{verdict, rejection_type?, rejection_detail?, target_stage?, scene_annotations?}` |
| `code_generated` | CodeWorker | `{success, error?}` |
| `code_review` | 审核 API | 同上 |
| `render_completed` | RenderWorker | `{success, task_id?, asset_id?, code_version_id?, code_version_number?, error?}` |
| `video_review` | 审核 API | 同上 |
| `cancel` | 预留 | `{reason?}`（尚未接入主循环） |

### 1.3 Worker 消费模型

Worker（`backend/app/workers/{narrative_worker,code_worker,render_worker,base}.py`）不是 Temporal Activity Worker，而是轮询 `worker_tasks` 表的自建进程：activity 写入一条 `WorkerTask`，对应 Worker 轮询取到后执行（调用 AI/渲染引擎），完成后通过 Temporal Client 主动 signal 回工作流。

### 1.4 关键 Activities

- `submit_narrative_task`：查 `Topic`、查最近一次 `rejected` 事件作为驳回上下文、取上一版 scenes、调用 `build_prompt_snapshot()` 生成并冻结 Prompt 快照，写入 `WorkerTask(task_type="generate_narrative")`。
- `submit_code_task`：**直接复用** `NarrativeVersion.prompt_snapshot`（不重新解析 `style_config`），保证叙事/代码两阶段用同一版提示词。
- `submit_video_generation_task`：把 `project.current_code_version_id` 冻结到任务的 `code_version_id` 字段，避免渲染期间项目指针被后续改动影响本次任务。
- `check_and_increment_retry`：`retry_count += 1`，超过 1 次重试（即总共尝试 2 次）判定失败。
- `reset_stuck_stage`：人工"重置卡死阶段"，仅允许对 `narrative_generating`/`code_generating`/`code_failed`/`video_generating` 生效，取消未完成的 `WorkerTask` 并重新提交。

## 2. 三道人工审核闸门

统一入口：`POST /api/projects/{project_id}/review`，请求体含 `gate`（narrative/code/video）、`verdict`（approved/rejected/abandoned）、`rejection_type?`、`rejection_detail?`、`target_stage?`、`scene_annotations?`，以及内容编辑字段 `edited_scenes`/`edited_code_scenes`/`fact_check_verdicts`。

**约束**：先向 Temporal 发送 signal，**只有 signal 发送成功才落库** `ProjectEvent(event_type="review_verdict")`，避免出现"记录了审核结果但工作流没收到"的假成功；事件记录里绑定 `content_version_id`/`content_version_number`，支撑时间线回溯。

### 2.1 narrative 闸门
- 审核人若编辑了镜头（`edited_scenes`），按 `scene_index` 合并到当前 `NarrativeVersion.scenes`。
- **硬约束**：若编辑改动了 `beats[].cue_text`（旁白文字），直接返回 409——因为 TTS 音频已基于原文字生成，文字变了必须重新走生成流程，不允许绕过。
- 校验通过后**新建一个版本号**的 `NarrativeVersion`（不是原地改），`project.current_narrative_version_id` 指向新版本。
- `verdict=approved` 时额外校验 `validate_scenes_for_codegen()`（例如所有镜头 TTS 状态是否就绪），不满足返回 422。

### 2.2 code 闸门
- 支持编辑 `fact_check_verdicts`（逐条事实核查打 approved/rejected/needs_revision + note）和 `edited_code_scenes`（直接改某镜头代码）。
- 同样是新建版本号的 `CodeVersion`，`project.current_code_version_id` 指向新版本。

产品设计原则（承自 PRD）：事实核查表是审核的主要工作面——`confidence=low` 且 `is_hypothesis=false` 的条目理应全部过审才允许进入视频生成，但**此规则目前只靠人工约束，代码里未见强制校验**。

### 2.3 video 闸门
- 视频已渲染完成，没有可编辑内容，直接发送 signal。
- 驳回时可携带 `scene_annotations`（针对具体镜头标注问题）+ `target_stage`。

### 2.4 设计原则

把判断压向便宜的闸门：narrative/code 两道内容闸门应严格把关，通过后内容原则上冻结；video 闸门只管执行质量（渲染是否符合已批准的脚本/代码），驳回只有"退回重写"或"废弃"两条路，不在这一层重新讨论内容对错。

## 3. Prompt 提示词体系

系统提示词分两层：**风格组件**（用户可编辑，存 DB，四类）+ **系统骨架**（写死在代码/yaml，不可编辑）。生成叙事时两者拼合成一份 `prompt_snapshot` 并冻结进版本记录，保证跨版本可复现、可追溯。

### 3.1 四类风格组件（`prompt_components` 表）

| 类别 | 中文标签 | 内容 |
|---|---|---|
| `narrative_style` | 叙事蓝图 | 叙事风格 + 节奏 + 镜头结构，三合一 |
| `color_scheme` | 视觉系统 | 配色系统 |
| `animation_style` | 动画系统 | 动画/视觉精致度规范 |
| `exemplar` | 金样本 | 完整 JSON 输出结构范例（含 scene/beats 示例） |

`VideoProject.style_config`（JSONB）为每类各绑定一个 `prompt_component_id`，未绑定时使用系统默认（写死在 `ChatAIProvider._DEFAULT_STYLE_COMPONENTS`）。用户可在"风格提示词工作台"用 AI 辅助生成/迭代（见 §3.6(f)）。

### 3.2 Prompt 快照机制（`services/prompt_bundle.py: build_prompt_snapshot`）

- 提交叙事生成任务时，解析 `style_config` 得到四类组件实际文本 + 各自 `sha256`/`updated_at`，连同 `engine_spec_sha256`（引擎专属 yaml 的哈希）、`BASE_PROMPT_VERSION="blueprint-exemplar-v1"` 打包写入 `NarrativeVersion.prompt_snapshot`。
- 代码生成阶段**不重新读取 `style_config`**，而是用 `style_components_from_snapshot()` 从叙事版本的快照还原——即使用户在此期间改了风格组件库，代码生成仍使用生成叙事时那一版提示词。
- 这是可追溯性的核心：每个版本都记录了生成它当时用的是哪版提示词。

### 3.3 叙事生成 system prompt（`ChatAIProvider._build_narrative_system_prompt`）

结构（依次拼接）：
1. 角色声明：知识视频叙事脚本生成器，严格输出 JSON
2. 【输出格式与风格范例】：注入 `exemplar` 组件（完整 JSON 示例）
3. 依次注入 `narrative_style`（叙事蓝图）→ `color_scheme`（配色+颜色名对照提示）
4. 【语义节拍契约】：`beats` 必须存在、`cue_text` 须逐字取自 narration 且顺序覆盖全文、`transition` 枚举值（continue/transform/reveal/replace/exit）
5. 引擎专属 `narrative_hint`（来自 `engine_specs/*.yaml`）
6. 画幅与构图规范（横屏/竖屏排版 + 对应引擎坐标系提示）
7. 收尾要求（首镜头设背景色、scene_index 连续递增、元素及时退场、fact_checks 覆盖关键论断、镜头数/时长满足叙事蓝图等）+ JSON 转义规则（禁止英文直引号，需用中文书名号/引号）

输入变量：`topic_title`, `topic_description`, `render_engine`, `aspect_ratio`, `rejection_context?`, `previous_scenes?`（驳回重生成时的上一版）, `narrative_context`（创作者标注的参考资料）, `style_components`。

生成结果经 `services/narrative_validator.py: validate_and_normalize_scenes()` 校验，失败最多重试 1 次，校验错误列表回传模型要求修正。

### 3.4 代码生成 system prompt（`ChatAIProvider._build_code_system_prompt`）

结构：
1. 角色声明 + 输出格式 `{"codes": [...]}`
2. 【硬性约束：镜头数量】codes 数组长度必须与 scenes 一一对应，禁止合并/跳过
3. 注入 `color_scheme`、`animation_style`
4. 【语义节拍时间执行契约】beats 已带真实 speech 时间，动画须覆盖时间窗口 70% 以上，关键视觉结果需在 `speech_end_seconds` 前出现
5. 引擎专属 `code_prompt`（yaml）
6. 画幅构图规范
7. 【代码拼合规则】各镜头片段将被顺序拼合，音频由渲染引擎注入
8. 【音画同步规则】动画总时长 ≤ `duration_seconds`，不低于其 85%（目标 90-100%）
9. 【遗留元素处理】镜头开场先处理上一镜头遗留元素退场
10. 收尾：严格按 description 实现、跨镜头变量复用、不写外层结构 + JSON 转义规则

输入变量：`scenes`（narration/description/duration_seconds/beats/code）、`render_engine`、`style_components`、`aspect_ratio`、`rejection_context?`、`previous_code_scenes?`。

### 3.5 引擎专属 Prompt 片段（`engines/ai/engine_specs/{manim,remotion}.yaml`）

每个 yaml 含两段：
- `narrative_hint`：注入叙事 prompt，规定 description/visual_action 只写画面意图（禁止代码语法），给出"画面描述契约五要素"（初始状态/元素清单/动画时序/状态语义/结束定格）+ 正反例 + beat 动画密度要求。
- `code_prompt`：注入代码 prompt，引擎特定详尽规范：
  - **Manim**：版本锁定（Community v0.20.1）、高频报错清单（如 `set_stroke` 不支持 dash 参数）、代码片段格式（只写 `construct()` 方法体）、动画窗口填充率、变量跨镜头生命周期、画布安全区坐标、`Axes` 防溢出、中文必须用 `Text()` 不能用 `MathTex()`、禁止引用外部图片/SVG、退场检查清单等。
  - **Remotion**：具名 React 组件片段规范、语义节拍→帧窗口换算、可用 API 清单（`AbsoluteFill`/`Sequence`/`Audio`/`interpolate`/`spring`）、画布 1280×720、Tailwind 静态样式 + 内联动态样式分工规则。

### 3.6 其他 Prompt

- **(c) 代码修复**（`repair_code()`，内联 f-string）：角色"知识视频渲染代码修复专家"。输入一次整体渲染失败的完整错误信息 + 全部镜头（剥离 TTS 专用字段）。输出 `{"repairs":[{scene_index, code, explanation}]}`，仅修改需要修复的镜头，保持旁白/画面意图/跨镜头变量关系不变。CodeWorker 最多循环 2 轮"验证失败 → AI 修复 → 再验证"（`_MAX_VALIDATION_ROUNDS = 2`）。
- **(d) 选题头脑风暴**（`brainstorm_topics()`）：角色"知识视频选题策划助手"。输出 `{"candidates":[{title, description, tags}]}`。输入 `topic_direction`、`count`。
- **(e) 选题研究对话**（`research_topic()`，流式）：默认 system prompt"基于事实、理论背景和可视化潜力回答，输出 Markdown"，支持自定义 `system_prompt` 覆盖。输入 `topic_title`, `topic_description`, `conversation_history`, `new_message`。
- **(f) 风格提示词工作台辅助**（`assist_style_prompt()`）：角色"知识视频生产系统的风格提示词设计助手"，通过多轮对话把用户想法整理为可执行的风格组件提示词（只改当前组件类型范围内规则、避免空泛形容词）。输出 `{reply, name, description, prompt_text}`。

### 3.7 Structured Output

`engines/ai/structured_output.py` 定义各任务 JSON Schema（`NARRATIVE_SCHEMA`/`CODE_GENERATION_SCHEMA`/`CODE_REPAIR_SCHEMA`/`BRAINSTORM_SCHEMA`/`STYLE_ASSISTANT_SCHEMA`），`response_format_for()` 按不同 Provider（OpenRouter/Gemini/DeepSeek/Doubao）适配是否支持原生 JSON Schema 强约束。

## 4. 引擎层职责与调用关系

### 4.1 `engines/ai/`
`AIProvider` Protocol（`generate_narrative`/`generate_code`/`repair_code`/`brainstorm_topics`/`research_topic`/`assist_style_prompt`）→ `ChatAIProvider`（Prompt 拼装核心）→ 包裹具体厂商 `ChatClient`（`openrouter.py`/`gemini.py`/`deepseek.py`/`doubao.py`）→ 经 `RecordingChatClient` 审计包装（记录到 `AICallRecord`：输入/输出/token/费用/耗时/状态）→ 发出 HTTP 请求。`factory.py: get_ai_provider(business_name)` 按业务场景（narrative_generation/code_generation/code_repair/topic_brainstorm/topic_research/style_assistant）查 `AIModelConfig` 决定厂商/模型。

### 4.2 `engines/tts/`
`TTSEngine` Protocol，`volcengine.py`（火山引擎/豆包实现，返回带词级时间戳的合成结果）。`NarrativeWorker._synthesize_scenes_tts()` 在叙事生成后对每镜头并发（信号量=3）调 TTS，结果合并回 scenes，再交给 `services/beat_aligner.align_scene_beats()`：用 `difflib` 把 `beats[].cue_text` 与词级时间戳对齐，计算 `speech_start/end_seconds`（真实朗读时间）与 `animation_start/end_seconds`（加 pre/post-roll 缓冲，Manim 为 0.18s/0.12s），未能对齐的 beat 标记 `interpolated/pending/failed` 并按权重插值兜底。这套"beat 时间线"正是代码生成 prompt 中"语义节拍时间执行契约"消费的数据。

### 4.3 `engines/render/`
`RenderEngine` Protocol（`validate_code`/`render`/`health_check`）。`manim.py` 把各镜头代码拼合进统一 `Scene.construct()`，用 `self.add_sound()` 注入音频；`remotion.py` 把各镜头代码拼成具名 React 组件注入 Remotion 项目模板。`CodeWorker` 生成代码后调用 `validate_code()` 做自愈循环（见 §3.6(c)），验证通过才写入 `CodeVersion`；`RenderWorker` 在视频生成阶段下载各镜头音频、调 `render()` 得到完整 mp4，上传对象存储，更新 `VideoAsset`。

## 5. 关键数据模型

### 5.1 `video_projects`
`id`, `topic_id`, `status`（当前状态机状态）, `render_engine`（manim/remotion）, `tts_voice`/`tts_engine`/`tts_speed`, `aspect_ratio`, `current_narrative_version_id`/`current_code_version_id`/`current_video_asset_id`（指向当前有效版本的可变指针，历史版本仍保留在各自表中）, `temporal_workflow_id`, `retry_count`, `narrative_context`（JSONB list，创作者标注的参考资料）, `style_config`（JSONB，四类组件绑定）。

### 5.2 `scenes` 结构（存于 `NarrativeVersion.scenes`/`CodeVersion.scenes`，JSONB）
叙事阶段：`scene_index`, `narration`, `description`, `duration_seconds`, `beats: [{beat_index, cue_text, visual_action, emphasis, transition, fallback_weight, speech_start_seconds, speech_end_seconds, animation_start_seconds, animation_end_seconds, alignment_status}]`, TTS 相关（`tts_status`/`audio_key`/`duration_seconds`/`word_timestamps`）。代码阶段追加 `code` 字段。

`fact_checks` 条目：`claim_text, scene_index, source_url?, source_description, confidence(high/medium/low), is_hypothesis, assumptions?, controversy?, reviewer_verdict?, reviewer_note?`。

### 5.3 版本/资产/日志表
- `narrative_versions`：`project_id, version_number, scenes, fact_checks, ai_model, rejection_context, prompt_snapshot, created_at`
- `code_versions`：同上结构 + `render_engine`
- `video_assets`：`project_id, code_version_id, video_file_key, duration_seconds, resolution, render_log, error_message, status`
- `project_events`：不可变追加日志，`event_type`（status_change/review_verdict/stuck_reset）, `from_status, to_status, actor, payload`
- `worker_tasks`：机器任务队列
- 其余：`topics`, `performance_records`, `prompt_components`, `style_templates`, `ai_model_config`, `ai_call_records`

## 6. 与既有文档的关系

- `docs/PRD_产品需求文档.md` 3.2 节的状态机图与本文一致，是最贴近实现的权威描述，可直接引用；但 3.5 节"闸门①/闸门②"的两闸门概念需理解为已演进成当前的 narrative_review + code_review 两个独立闸门。
- `docs/TECH_技术实现方案.md` 4.2 节工作流伪代码、3 节表结构（缺 `narrative_versions` 表）均是叙事/代码尚未拆分为两阶段之前的早期版本，**已过时**，请以本文档 + 源码为准。
