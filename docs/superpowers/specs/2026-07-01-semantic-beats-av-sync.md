# 语义节拍（Beats）与字符级音画同步技术实现方案

**日期：** 2026-07-01  
**状态：** 已实现（2026-07-02）
**关联方案：** `docs/superpowers/specs/2026-07-01-prompt-system-redesign.md`

---

## 1. 背景

当前视频生产链路以镜头为最小原子单位：

```text
选题
  → AI 生成 scenes[narration + description]
  → 按镜头生成 TTS
  → AI 将每个 description 转换为 Manim/Remotion code
  → 所有镜头代码整体渲染
```

该设计能够保证脚本审核、TTS、代码生成和整体渲染顺利衔接，但 `description` 只表达镜头级画面意图，不能明确描述一个 10～15 秒镜头内部：

- 哪句旁白对应哪次视觉变化；
- 动画应在什么时候开始和结束；
- 哪个元素是当前语义重点；
- 前一动作如何转化为后一动作；
- 什么时候应该保持、替换或退场。

因此代码生成模型容易在镜头开头完成全部进场动画，随后停留静态画面等待旁白结束，最终形成“自动播放 PPT”式节奏。

火山 TTS 的流式响应已经提供字符/词级时间戳：

```json
{
  "sentence": {
    "text": "你好，语音测试",
    "words": [
      {
        "word": "你",
        "startTime": 0.195,
        "endTime": 0.335,
        "confidence": 0.89597625
      }
    ]
  }
}
```

本方案利用该时间戳，在现有 `scene` 内新增 `beats[]`，建立：

```text
旁白语义片段 → 字符时间区间 → 视觉动作 → 渲染代码时间线
```

---

## 2. 目标

1. 保持 `scene` 为 TTS、审核、代码生成和渲染的基本单位。
2. 用 `beats[]` 表达镜头内部 2～4 个语义节拍。
3. 利用火山 TTS 字符时间戳计算每个 beat 的真实语音时间。
4. 让 Manim 和 Remotion 代码按语义时间执行，而不是只在镜头开头播放进场动画。
5. 将 `beats` 设为新叙事数据的强制契约，不维护无 beats 的双生成链路。
6. 明确提示词的固定部分与平台可变部分，避免重复约束和风格冲突。
7. 保存本次生成实际使用的提示词快照，使结果可审计、可复现。

---

## 3. 非目标

本次不做：

- 将 beat 拆成独立 Manim Scene 或 Remotion Sequence；
- 按 beat 单独生成并拼接 TTS；
- 修改“两道人工审核闸门不可跳过”的工作流；
- 引入完整的非线性时间线编辑器；
- 自动生成背景音乐或音效；
- 将全部代码生成改造成多 Agent 或逐 beat 调用；

---

## 4. 核心设计原则

### 4.1 Scene 是原子单位，Beat 是内部时间表

`beat` 不是新镜头，也不是新的渲染任务：

```text
Scene 4（14.2 秒）
├── Beat 0：出现一个旁观者
├── Beat 1：责任值升至 100%
├── Beat 2：旁观者增加为十人
└── Beat 3：责任分裂为十份
```

一个 scene 仍然：

- 生成一个音频文件；
- 生成一段 Manim/Remotion 代码；
- 在审核页作为一个镜头展示；
- 在渲染阶段作为一个 `SceneInput`。

### 4.2 LLM 负责语义，系统负责时间

LLM 生成：

- `cue_text`；
- `visual_action`；
- `emphasis`；
- `transition`；
- 可选的回退时长权重。

系统根据 TTS 时间戳生成：

- 字符起止位置；
- 语音起止时间；
- 建议动画起止时间；
- 对齐状态与覆盖率。

禁止让 LLM 猜测绝对秒数。

### 4.3 固定契约与可变风格分离

以下属于系统正确性，必须放在代码或引擎 YAML 中：

- JSON Schema；
- beat 字段语义；
- `cue_text` 覆盖旁白的规则；
- 字符时间戳的使用规则；
- 音画同步规则；
- Manim/Remotion 技术约束；
- 输出格式、校验和回退行为。

以下属于创作选择，应继续由平台 `prompt_components` 管理：

- 叙事语气与叙事风格；
- 目标时长与信息密度；
- 内容结构；
- 配色系统；
- 动画审美与视觉语言。

平台组件不得包含 `LaggedStart`、`useCurrentFrame`、`fill_opacity` 等引擎实现细节；这些内容属于引擎 YAML。

### 4.4 原始时间与演出时间分开

每个 beat 保存两组时间：

- `speech_start/end_seconds`：TTS 的客观时间；
- `animation_start/end_seconds`：应用视觉提前量、延后量之后的演出时间。

这样既保留原始数据，又允许不同动画风格采用不同的视觉预读节奏。

---

## 5. 总体架构

```text
┌──────────────────────────────────────────────┐
│ Prompt Bundle                                │
│ 固定叙事契约 + 平台风格组件 + 引擎叙事规范   │
└───────────────────────┬──────────────────────┘
                        │
                        ▼
              Narrative AI Provider
                        │
                        ▼
     scenes[narration + description + beats]
                        │
                        ▼
                  NarrativeWorker
                        │
                火山 TTS（scene 级）
                        │
          audio + duration + word timestamps
                        │
                        ▼
                 BeatAligner
          cue_text → 字符区间 → 语音时间
                        │
                        ▼
      scenes[resolved beats + scene audio]
                        │
              人工脚本/旁白审核
                        │
                        ▼
                   CodeWorker
                        │
   固定代码契约 + 平台视觉组件 + 引擎代码规范
                        │
                        ▼
       每个 scene 生成一段带时间线的 code
                        │
                        ▼
           Manim / Remotion 整体渲染
```

---

## 6. 数据模型

### 6.1 Pydantic Schema

修改 `backend/app/schemas/narrative.py`：

```python
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class WordTimestampSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    word: str
    start_time: float
    end_time: float
    confidence: Optional[float] = None


class NarrativeBeatSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    # AI 生成字段
    beat_index: int
    cue_text: str
    visual_action: str
    emphasis: Optional[str] = None
    transition: Literal[
        "continue",
        "transform",
        "reveal",
        "replace",
        "exit",
    ] = "continue"
    fallback_weight: float = 1.0

    # 系统派生字段
    cue_start_char: Optional[int] = None
    cue_end_char: Optional[int] = None
    speech_start_seconds: Optional[float] = None
    speech_end_seconds: Optional[float] = None
    animation_start_seconds: Optional[float] = None
    animation_end_seconds: Optional[float] = None
    alignment_status: Literal[
        "pending",
        "aligned",
        "interpolated",
        "failed",
    ] = "pending"


class NarrativeSceneSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    scene_index: int
    narration: str
    description: str
    beats: list[NarrativeBeatSchema] = Field(default_factory=list)

    estimated_duration_seconds: Optional[float] = None
    audio_key: Optional[str] = None
    duration_seconds: Optional[float] = None
    tts_status: Optional[str] = None
    audio_presigned_url: Optional[str] = None

    word_timestamps: list[WordTimestampSchema] = Field(default_factory=list)
    alignment_coverage: Optional[float] = None
    content_schema_version: int = 2
```

### 6.2 字段所有权

| 字段 | 生成者 | 是否允许人工编辑 |
|---|---|---|
| `narration` | AI/审核人 | 是 |
| `description` | AI/审核人 | 是 |
| `beat_index` | AI，后端重排 | 否 |
| `cue_text` | AI/审核人 | 是 |
| `visual_action` | AI/审核人 | 是 |
| `emphasis` | AI/审核人 | 是 |
| `transition` | AI/审核人 | 是 |
| `fallback_weight` | AI/审核人 | 可选 |
| `cue_start/end_char` | BeatAligner | 否 |
| `speech_start/end_seconds` | BeatAligner | 否 |
| `animation_start/end_seconds` | BeatAligner | 否 |
| `word_timestamps` | TTS 引擎 | 否 |
| `alignment_coverage` | BeatAligner | 否 |

### 6.3 JSONB 与数据库迁移

`NarrativeVersion.scenes` 和 `ScriptVersion.scenes` 已是 JSONB，因此增加 beats、时间戳和对齐字段不需要数据库迁移。

项目尚处于开发初期，不保留无 beats 的兼容分支。所有新生成和人工提交的 scene 必须满足 `content_schema_version=2` 且 `beats` 非空；缺失 beats 视为数据校验失败，不进入代码生成。

### 6.4 提示词快照

平台中的自定义 `prompt_components` 可被修改。当前叙事任务和代码任务分别从数据库读取组件文本，人工审核等待期间如果组件被修改，两个阶段可能使用不同版本的风格。

建议新增迁移：

```sql
ALTER TABLE narrative_versions ADD COLUMN prompt_snapshot JSONB;
ALTER TABLE script_versions ADD COLUMN prompt_snapshot JSONB;
```

快照格式：

```json
{
  "base_prompt_version": "semantic-beats-v1",
  "render_engine": "manim",
  "engine_spec_sha256": "…",
  "components": {
    "narrative_style": {
      "id": "…",
      "name": "情境驱动知识叙事",
      "prompt_text": "…",
      "updated_at": "2026-07-01T10:00:00Z",
      "sha256": "…"
    }
  }
}
```

规则：

1. 提交 `generate_narrative` 任务时解析全部组件并形成完整快照。
2. `NarrativeWorker` 将快照写入 `NarrativeVersion.prompt_snapshot`。
3. 后续 `generate_code` 从当前 narrative version 读取同一快照，不重新读取可变组件文本。
4. 驳回并重新生成 narrative 时创建新快照。
5. `ScriptVersion` 保存最终使用的同一快照。

这样既允许平台组件继续演进，又保证同一内容版本的生成过程可复现。

---

## 7. Narrative 输出契约

### 7.1 示例

```json
{
  "scene_index": 4,
  "narration": "如果现场只有你一个人，责任几乎全部落在你身上。但周围站着十个人时，每个人都会觉得别人可能先行动。",
  "description": "用人数增加导致个人责任下降的动态图示解释责任分散。",
  "estimated_duration_seconds": 13.0,
  "beats": [
    {
      "beat_index": 0,
      "cue_text": "如果现场只有你一个人，",
      "visual_action": "中央出现一个旁观者，周围空间保持空旷，责任计量环开始出现。",
      "emphasis": "唯一旁观者",
      "transition": "reveal",
      "fallback_weight": 1.0
    },
    {
      "beat_index": 1,
      "cue_text": "责任几乎全部落在你身上。",
      "visual_action": "责任计量环由0增长到100%，旁观者成为画面唯一高亮主体。",
      "emphasis": "100%责任",
      "transition": "continue",
      "fallback_weight": 1.0
    },
    {
      "beat_index": 2,
      "cue_text": "但周围站着十个人时，",
      "visual_action": "一个旁观者复制并扩展为十人，围绕求助者形成环形关系。",
      "emphasis": "人数增加",
      "transition": "transform",
      "fallback_weight": 1.3
    },
    {
      "beat_index": 3,
      "cue_text": "每个人都会觉得别人可能先行动。",
      "visual_action": "100%责任分裂为十份，众人的视线依次转向其他人，求助者高亮逐渐减弱。",
      "emphasis": "责任分散",
      "transition": "transform",
      "fallback_weight": 1.7
    }
  ]
}
```

### 7.2 强约束

对于新生成的 schema v2 scene：

1. `beat_index` 从 0 连续递增。
2. 标题/结尾镜头允许 1～2 个 beat，普通镜头应有 2～4 个 beat。
3. `cue_text` 必须是 `narration` 中按顺序出现的原文，不得改写或概括。
4. 连接全部 `cue_text` 并忽略空白差异后，应完整覆盖 `narration`。
5. 每个 beat 必须产生新的知识信息、关系变化或叙事状态；不得用“保持画面”凑数量。
6. `visual_action` 描述画面意图，不得出现 Manim/React/Remotion API。
7. `description` 保留为镜头级整体意图，`beats` 负责镜头内部动作与时间线；两者都是代码生成输入。

### 7.3 Narrative 校验与修复

新增：

```text
backend/app/services/narrative_validator.py
```

校验项：

- scene index 连续；
- beat index 连续；
- cue 覆盖率；
- cue 顺序；
- 空 cue；
- 空 visual action；
- beat 数量；
- `fallback_weight > 0`；
- 总旁白字数和目标时长约束。

处理策略：

| 问题 | 行为 |
|---|---|
| beat index 不连续 | 后端自动重排 |
| cue 仅有空白差异 | 后端规范化 |
| cue 覆盖率 ≥ 95% | 尾部未覆盖文本合并进最后一个 beat |
| cue 覆盖率 < 95% | 调用一次 narrative JSON 修复 |
| 修复后仍失败 | narrative 任务失败，进入 Worker 既有重试/失败流程，不产生不完整版本 |

---

## 8. 火山 TTS 时间戳采集

### 8.1 TTSResult 扩展

修改 `backend/app/engines/tts/base.py`：

```python
@dataclass
class WordTimestamp:
    word: str
    start_time: float
    end_time: float
    confidence: float | None = None


@dataclass
class TTSResult:
    success: bool
    output_path: str | None
    duration_seconds: float | None
    error_message: str | None
    audio_bytes: bytes = field(default=b"")
    word_timestamps: list[WordTimestamp] = field(default_factory=list)
```

### 8.2 Volcengine 解析

修改 `backend/app/engines/tts/volcengine.py`，在收集音频 chunk 的同时收集：

```python
sentence = chunk.get("sentence") or {}
for item in sentence.get("words") or []:
    timestamps.append(
        WordTimestamp(
            word=item["word"],
            start_time=float(item["startTime"]),
            end_time=float(item["endTime"]),
            confidence=item.get("confidence"),
        )
    )
```

流式响应可能重复返回 sentence 元数据，使用以下键去重：

```python
(word, round(start_time, 6), round(end_time, 6))
```

完成后：

1. 按 `start_time/end_time` 排序；
2. 删除完全重复项；
3. 检查时间单调性；
4. 将负值裁剪为 0；
5. 将超出音频时长的值裁剪到 `duration_seconds`；
6. 保留低置信度时间戳，但记录覆盖率，不因单个低置信度字符中断 TTS。

### 8.3 NarrativeWorker

`_synthesize_scenes_tts()` 将时间戳写回 scene，随后调用 BeatAligner：

```python
scene_with_audio = {
    **scene,
    "tts_status": "ready",
    "audio_key": key,
    "duration_seconds": result.duration_seconds,
    "word_timestamps": [asdict(item) for item in result.word_timestamps],
}

return align_scene_beats(scene_with_audio)
```

TTS 失败时：

- 保留 AI 生成 beats；
- `alignment_status` 保持 `pending`；
- 不生成虚假的绝对时间；
- 原有失败处理保持不变。

---

## 9. Beat 对齐算法

新增：

```text
backend/app/services/beat_aligner.py
```

### 9.1 文本规范化

不能简单删除字符后直接使用新下标，必须保留“规范化字符 → 原文字符”的索引映射。

统一规则：

- Unicode NFKC；
- 忽略空格、制表符和换行；
- 中文全角/半角标点统一；
- 保留标点参与顺序对齐；
- 不改变汉字、数字和英文字母内容。

输出：

```python
NormalizedText(
    text="如果现场只有你一个人，责任……",
    original_indices=[0, 1, 2, ...],
)
```

### 9.2 Cue 字符区间

优先使用“cue 完整分割 narration”的契约计算字符区间，而不是在 narration 中独立执行不受约束的模糊搜索，避免重复短语匹配到错误位置。

```text
narration:
  如果现场只有你一个人，责任几乎全部落在你身上。

beat 0:
  如果现场只有你一个人，
  → [0, 12)

beat 1:
  责任几乎全部落在你身上。
  → [12, 26)
```

### 9.3 TTS token 映射

火山字段名为 `words`，但一个 token 可能包含多个字符，例如 `"好，"`。构建：

```python
TokenSpan(
    normalized_start_char=1,
    normalized_end_char=3,
    start_time=0.335,
    end_time=0.725,
)
```

如果 beat 边界落在多字符 token 内，使用整个 token 的起止时间，不对 token 内部时间做无依据的平均切分。

### 9.4 单调序列对齐

对 narration 规范化字符序列和 TTS token 展开字符序列执行单调对齐：

1. 完全一致时直接按下标映射；
2. 存在标点或空白差异时使用顺序匹配；
3. 不允许后一个 beat 映射到前一个 beat 之前；
4. 每个 beat 取第一个重叠 token 的 `start_time`；
5. 每个 beat 取最后一个重叠 token 的 `end_time`。

建议使用标准库 `difflib.SequenceMatcher`，不增加新依赖。

### 9.5 回退策略

| 情况 | 策略 |
|---|---|
| 全部 cue 对齐 | `alignment_status=aligned` |
| 部分 beat 对齐 | 已对齐 beat 作为锚点，缺失区间按 `fallback_weight` 插值 |
| 无任何时间戳 | 按 cue 字数和 `fallback_weight` 分配总音频时长 |
| TTS 时长缺失 | 不生成 timing，`alignment_status=failed` |

`alignment_coverage`：

```text
已映射的规范化 narration 字符数 / narration 规范化总字符数
```

质量阈值：

- `>= 0.95`：正常；
- `0.80～0.95`：允许生成，记录 warning；
- `< 0.80`：按权重回退，并记录 error metric。

### 9.6 演出时间

默认规则属于固定代码配置：

```python
ANIMATION_PREROLL_SECONDS = 0.18
ANIMATION_POSTROLL_SECONDS = 0.12
```

```python
animation_start = max(0, speech_start - preroll)
animation_end = min(scene_duration, speech_end + postroll)
```

允许相邻 beat 的演出时间轻微重叠，以形成自然衔接。原始 speech 时间永远不被覆盖。

平台 `animation_style` 可以描述“动作更利落”或“动作更舒缓”，但不能修改原始语音时间；代码生成模型根据风格在演出窗口内分配运动。

---

## 10. 审核与编辑

### 10.1 权威文本

为了避免 `narration` 与 `beats[].cue_text` 成为两个相互冲突的来源：

- 后端持久化时以 `beats[].cue_text` 顺序拼接结果作为 scene narration；
- `narration` 是便于接口、TTS 和前端读取的物化字段；
- `beats` 必须存在，服务端不接受只有 narration 而没有 beats 的 schema v2 scene。

### 10.2 前端审核页

修改 `NarrativeReviewPanel`：

- scene 顶部展示完整旁白和音频；
- 下方以折叠卡片展示 beats；
- 每个 beat 可编辑 `cue_text`、`visual_action`、`emphasis` 和 `transition`；
- 展示语音时间区间与对齐状态；
- 修改任一 `cue_text` 后标记 scene 的 TTS 与 alignment 为 dirty；
- 修改纯 `visual_action` 不需要重新生成 TTS，只需重新生成代码；
- 点击“重新生成音频”时传递完整 beats，由后端重新拼接 narration、生成 TTS 和对齐。

### 10.3 API

扩展 `EditedNarrativeScene`：

```python
class EditedNarrativeScene(BaseModel):
    scene_index: int
    narration: str
    description: str
    beats: list[NarrativeBeatSchema] = []
    estimated_duration_seconds: Optional[float] = None
```

扩展单镜头 TTS 请求：

```python
class RegenerateTtsRequest(BaseModel):
    scene_index: int
    narration: str
    beats: list[NarrativeBeatSchema] = []
```

服务端：

1. 校验 cue 覆盖；
2. 从 beats 重新构造 narration；
3. 生成 TTS；
4. 保存 word timestamps；
5. 重新运行 BeatAligner；
6. 返回 resolved beats、音频 URL、时长和对齐覆盖率。

客户端不传 beats 时返回 422，不生成不完整的 narrative version。

---

## 11. 提示词拼接改造

### 11.1 Prompt Bundle

新增内部结构：

```python
@dataclass
class PromptBundle:
    base_prompt_version: str
    render_engine: str
    components: dict[str, str]
    component_metadata: dict[str, dict]
    engine_narrative_hint: str
    engine_code_prompt: str
```

Provider 仍不直接访问数据库。Activity 负责解析平台组件并将 bundle/snapshot 放入任务 payload。

### 11.2 Narrative Prompt 拼接顺序

```text
1. [固定] 角色、输出 JSON、顶层 Schema
2. [平台] narrative_style
3. [平台] pacing
4. [平台] scene_structure
5. [平台] color_scheme
6. [固定] Semantic Beat 输出契约
7. [引擎 YAML] narrative_hint（弱技术画面能力）
8. [固定] 事实核查、合法 JSON、最终检查清单
```

固定部分新增：

```text
【语义节拍契约】
- 每个 scene 除 narration、description 外必须输出 beats。
- 普通镜头输出 2～4 个 beats，纯标题或结尾镜头可输出 1～2 个。
- cue_text 必须逐字取自 narration，并按顺序完整覆盖 narration；不得概括、改写或遗漏。
- visual_action 只描述这一句旁白发生时画面产生的知识性变化。
- 每个 beat 必须推进信息、关系或状态，禁止用“保持画面”凑数量。
- 不输出绝对时间；时间由 TTS 完成后计算。
- visual_action 不得出现任何渲染引擎 API、类名、组件名或代码语法。
```

注意：beat 数量、cue 契约和禁止绝对时间属于数据正确性，不放入平台可变 prompt。

### 11.3 Code Prompt 拼接顺序

```text
1. [固定] 角色、输出 JSON、codes 数组契约
2. [平台] color_scheme
3. [平台] animation_style
4. [固定] Semantic Beat 时间执行契约
5. [引擎 YAML] code_prompt
6. [固定] 代码拼合、音频注入、最终检查清单
```

固定部分新增：

```text
【语义节拍时间执行契约】
- scene 中 beats 已按顺序给出真实 speech 时间和建议 animation 时间。
- 每个 beat 的 visual_action 必须在自己的 animation 时间窗口内发生。
- 关键词对应的主要视觉结果最迟应在 speech_end_seconds 前清晰可见。
- 不得在第一个 beat 中一次性完成整个镜头的全部动画。
- 相邻 beat 优先通过已有元素的移动、变形、分裂、聚合或强调连续推进。
- 最后一个 beat 结束后可保持最终画面，但不得用无意义循环填满时间。
- 若某 beat alignment_status 为 interpolated，仍使用给出的时间；若为 failed，则由镜头总时长和 fallback_weight 顺序分配。
```

### 11.4 引擎 YAML 的责任

`manim.yaml` 新增“beat 时间翻译规则”：

- 按 beat 顺序维护镜头内时间游标；
- 用相邻窗口差值计算 `run_time` 和必要的 `wait`；
- `wait` 只用于等待下一语义锚点，不得把全部等待放在镜头末尾；
- 所有 play/wait 总时间不得超过 scene 音频时长；
- 前一 beat 的视觉结果默认作为后一 beat 的输入。

`remotion.yaml` 新增：

- `startFrame = round(animation_start_seconds * fps)`；
- `endFrame = round(animation_end_seconds * fps)`；
- 使用局部 frame 区间驱动每个 beat；
- 所有插值必须 clamp；
- 不得只用一个覆盖整个 `_sceneDuration` 的统一 spring 代替 beat 时间线。

### 11.5 避免把 TTS token 全量发送给代码模型

代码生成只需要 resolved beats，不需要字符级 `word_timestamps`。

`CodeWorker` 构造精简 payload：

```python
codegen_scenes = [
    {
        "scene_index": scene["scene_index"],
        "narration": scene["narration"],
        "description": scene["description"],
        "duration_seconds": scene.get("duration_seconds"),
        "beats": scene.get("beats") or [],
    }
    for scene in scenes
]
```

避免 15～20 个镜头的字符时间戳消耗上下文窗口。

---

## 12. 平台可变提示词：推荐示范版本

以下文本可直接作为新的内置 `prompt_components` 种子数据。它们只描述创作风格，不包含 JSON、beat 字段或引擎代码要求。

### 12.1 narrative_style：情境驱动知识叙事

**名称：** 情境驱动知识叙事  
**说明：** 先让观众进入具体问题，再通过证据和机制完成认知反转，适合心理学、行为科学和通识知识。

```text
【叙事风格：情境驱动知识叙事】

以一个观众能立即代入的具体处境、选择或冲突开场，不要先介绍术语、背景或定义。开头先让观众形成直觉判断，随后用事实、实验或反例制造认知反转，再解释背后的机制。

叙事推进遵循“发生了什么 → 直觉为什么会判断错 → 证据说明什么 → 机制如何运作 → 现实中怎么做”。抽象概念必须先通过人物、行为、空间关系或可观察结果呈现，再给出概念名称。

旁白使用自然、清晰、有画面感的现代口语。每句话只承担一个主要信息，不重复画面已经明确表达的内容，不使用空洞的过渡句、连续反问或夸张煽动。关键结论允许短句和停顿，形成认知落点。

保持可信和克制：不把相关性说成因果，不为戏剧效果歪曲实验结论；有争议或依赖条件的观点要明确边界。

结尾不要泛泛升华，应回到开头的具体处境，给出一个观众能够记住并执行的判断原则或行动方法。
```

### 12.2 pacing：高留存标准节奏（2.5 分钟）

**名称：** 高留存标准节奏（2.5 分钟）  
**说明：** 约 150 秒，控制总字数与段落密度，每 2～4 秒产生一次有效信息或视觉变化。

```text
【叙事节奏：高留存标准节奏】

目标成片时长为 140～170 秒，旁白总字数控制在 550～700 个中文字符，预计语速约为每秒 4.0～4.8 个中文字符。不要仅通过增加镜头数量控制时长。

全片建议 12～16 个镜头。普通镜头承担一个明确论点或过程，旁白通常为 25～45 个中文字符；复杂机制可以更长，但应拆成连续的语义阶段。纯标题镜头应极短，不得用长旁白停留在标题页。

前 6 秒必须出现具体问题、异常结果或需要观众判断的选择；前 20 秒内完成第一次信息反转或证据揭示。每 20～35 秒形成一次段落推进：新证据、新机制、新反例或新应用。

保持信息密度变化：冲突与证据段落更快，机制解释段落适度放缓，关键数字和结论前后允许短暂停顿。删除不增加信息的铺垫、同义重复、预告式句子和泛泛总结。

每个镜头内部应持续推进，约每 2～4 秒出现一次有意义的新信息、关系变化或视觉结果；变化必须服务理解，不能依赖无意义装饰维持热闹。
```

### 12.3 scene_structure：情境—证据—机制—行动

**名称：** 情境—证据—机制—行动  
**说明：** 从具体冲突切入，以实验或数据完成反转，随后解释机制并回到可执行行动。

```text
【内容结构：情境—证据—机制—行动】

第一段“情境与下注”（约全片 0%～12%）：
直接呈现一个具体人物、处境或选择，让观众在两个结果之间形成直觉判断。不要先展示视频标题、术语定义或作者介绍。

第二段“结果与证据”（约全片 12%～30%）：
尽快揭示反直觉结果，并用一个最有说服力的实验、数据、案例或对照支撑。证据必须说明比较对象、关键数字和结论边界。

第三段“机制拆解”（约全片 30%～68%）：
将核心机制拆成不超过三个相互衔接的步骤。每一步先展示可观察变化，再命名概念。优先表现因果链、状态变化、角色关系和数量变化，不连续堆叠定义。

第四段“现实迁移”（约全片 68%～88%）：
回到一个与观众有关的现实场景，对比常见错误做法和更有效做法。尽量复用开头场景，让知识发生可见的行为变化。

第五段“行动与回扣”（约全片 88%～100%）：
给出不超过三条、动作明确、可以立即执行的方法。最后一句回扣开头的问题，形成闭环，不另起空泛升华。

段落边界应通过证据揭晓、关系反转、视觉锚点变形或场景复用自然过渡，不使用孤立章节页反复打断叙事。
```

### 12.4 color_scheme：高对比亮底认知紫

**名称：** 高对比亮底认知紫  
**说明：** 延续现有紫色品牌感，提高主体尺寸、明度对比与移动端可读性。

```text
【视觉系统：高对比亮底认知紫】

基础背景：暖白 #FBFAFF；允许使用极浅紫 #F3EEFF 构建局部区域，但不得让整片长期处于同一低对比淡紫色。

主要文字：深墨紫 #211936；辅助文字：灰紫 #756A91。核心文字与背景必须保持清晰对比，避免大面积使用浅紫小字。

品牌主色：认知紫 #6C4FD4；高亮紫 #8B6FE8。主色用于当前叙事焦点、关键路径和核心概念，不把所有节点同时染成主色。

语义颜色：
- 风险/错误：#E85353
- 警示/待行动：#F39A3D
- 理性/解释：#258E9B
- 正确/完成：#25A85A
- 人物/情境辅助：#D96C9D

结构颜色：浅分隔线 #D9D0EE；深结构线 #51456F。

每个画面确定一个主导色和最多两个辅助语义色。红色只表达风险、错误或阻断，绿色只表达正确、完成或有效行动，不作纯装饰。

关键主体应具有足够面积和明度对比；核心数字、结论和当前动作必须在手机尺寸下优先可读。背景装饰降低透明度和复杂度，不与主体争夺注意力。
```

### 12.5 animation_style：语义驱动动态图解

**名称：** 语义驱动动态图解  
**说明：** 动画用于解释关系和过程，强调持续推进、视觉锚点与版式变化，避免模板化进场动画。

```text
【动画系统：语义驱动动态图解】

动画的首要职责是解释知识变化，而不是装饰页面。每次主要运动都必须对应旁白中的一个新事实、关系、数量、状态或行动结果。

镜头内部采用“建立对象 → 发生变化 → 显示结果”的推进方式。不要在镜头开始时一次性展示全部元素，也不要只播放进场动画后长时间静止。前一阶段的视觉结果应尽量成为后一阶段的输入，通过移动、连接、分裂、聚合、替换、对比或强调持续演化。

根据内容选择视觉语法：
- 人物与行为使用情境构图、视线、距离和行动路径；
- 原因与结果使用方向明确的因果链；
- 数量变化使用增长、分配、聚合和比例变化；
- 正误判断使用同一场景的前后对照；
- 实验与证据使用大数字、清晰对照和必要来源标识；
- 抽象机制使用状态变化，不用一组同质圆点代替所有概念。

构图避免长期居中和过度留白。核心主体通常占画面主要视觉区域；根据叙事在全屏情境、左右对比、局部特写、流程关系和数据证据等版式之间切换。版式变化服务段落层级，不随机切换。

转场优先复用视觉锚点：让上一画面的核心人物、数字、图形或路径变形成下一画面的解释对象。只有在主题真正切换时才整体淡出重建。

强调动作应短而明确，关键结果出现后留出可阅读时间。持续运动必须有语义，禁止用无意义循环、漂浮、呼吸或重复脉冲填满旁白时长。

装饰保持克制。光晕、阴影、弹性和粒子只用于突出当前重点，不作为所有镜头的统一模板。全片保持字体、圆角、线宽和图标语言一致。
```

---

## 13. CodeWorker 与代码生成

### 13.1 输入

`CodeWorker` 读取 aligned scenes，向 provider 传递精简数据：

```text
description 决定镜头整体意图；
beats 决定内部动作顺序与时间。
```

进入代码生成前必须校验每个 scene 的 beats 非空、索引连续且已得到 timing；任一 scene 不满足契约时，代码任务直接失败并报告具体 scene，不生成部分 codes。

### 13.2 输出保持不变

```json
{
  "codes": [
    "scene 0 code",
    "scene 1 code"
  ]
}
```

`CodeGenerationResult`、ScriptVersion 的 code 合并和渲染接口无需改变。

### 13.3 Token 风险

beats 会增加输入和输出复杂度。控制措施：

- 不向代码模型发送 `word_timestamps`、`audio_key`、`tts_status`；
- 普通 scene 限制 2～4 beats；
- `visual_action` 建议不超过 60 个中文字符；
- 目标 12～16 scenes；
- 记录代码响应 token 使用与截断错误；
- 第一阶段保持整体生成，若截断率超过 3%，再实施“分批代码生成 + 画布状态清单”。

---

## 14. Manim 与 Remotion 影响

### 14.1 Render API

`SceneInput` 无需新增 beats。渲染器消费的仍是最终 `code` 和 scene 音频：

```python
SceneInput(
    scene_index=...,
    narration=...,
    description=...,
    code=...,
    audio=...,
)
```

### 14.2 Manim

Manim 是顺序执行模型。代码生成器根据 beat 时间窗口维护相对时间游标：

```text
当前时间 < beat.animation_start
  → 等待差值

播放主要动画
  → run_time 不超过 beat 演出窗口

结果保持到下一 beat
```

需要重点校验：

- 总 `play + wait` 不超过音频时长；
- 不得把全部等待集中在 scene 尾部；
- 跨 beat 元素变量可复用；
- 跨 scene 变量规则保持现状。

### 14.3 Remotion

Remotion 直接将秒转换为局部帧：

```typescript
const startFrame = Math.round(beat.animationStartSeconds * fps);
const endFrame = Math.round(beat.animationEndSeconds * fps);
```

每个 beat 的动画使用自己的 frame 窗口，并对输入范围执行 clamp。

---

## 15. 可观测性与自动质检

### 15.1 生成指标

记录：

- 每个 scene 的 beat 数量；
- cue 覆盖率；
- TTS timestamp 数量；
- alignment coverage；
- aligned/interpolated/failed beat 数；
- scene 音频时长；
- 最长无新 beat 区间；
- narrative/code prompt 版本与 hash；
- 代码生成输出长度和修复轮数。

### 15.2 日志示例

```text
[BeatAligner] scene=4 beats=4 tokens=51 coverage=0.982 aligned=4 interpolated=0
[CodeWorker] scene=4 duration=13.42s beats=4 longest_gap=3.16s
```

日志不得打印完整 API Key、音频 Base64 或未脱敏的请求头。

### 15.3 渲染后节奏质检（后续增强）

使用 FFmpeg 每秒采样画面差异，检测：

- 连续低变化区间；
- 画面主体占比过小；
- 切换频率异常；
- 黑帧；
- 结尾意外长静止。

该质检不阻塞本次 beats MVP。

---

## 16. 文件改动清单

### 后端

| 文件 | 改动 |
|---|---|
| `app/schemas/narrative.py` | beats、timestamps、alignment schema |
| `app/schemas/project.py` | Script scene 输出 beats（如审核页需要） |
| `app/schemas/review.py` | 审核编辑 beats |
| `app/engines/tts/base.py` | `WordTimestamp`、扩展 `TTSResult` |
| `app/engines/tts/volcengine.py` | 解析 sentence.words |
| `app/services/beat_aligner.py` | 新增对齐算法 |
| `app/services/narrative_validator.py` | 新增 narrative/beat 校验 |
| `app/engines/ai/chat_provider.py` | 基础 prompt 契约与拼接顺序 |
| `app/engines/ai/engine_specs/manim.yaml` | Manim beat 时间翻译规则 |
| `app/engines/ai/engine_specs/remotion.yaml` | Remotion beat 时间翻译规则 |
| `app/workers/narrative_worker.py` | 保存 timestamp 并执行 alignment |
| `app/workers/code_worker.py` | 精简 codegen payload |
| `app/workflows/activities.py` | 构建并传递 prompt bundle/snapshot |
| `app/api/projects.py` | 单 scene TTS 重生成返回 resolved beats |
| `app/api/reviews.py` | 保存 beats，处理 dirty 状态 |
| `app/models/narrative_version.py` | `prompt_snapshot` |
| `app/models/script_version.py` | `prompt_snapshot` |
| `alembic/versions/*` | prompt snapshot 迁移、可选新内置组件 |

### 前端

| 文件 | 改动 |
|---|---|
| `src/types/index.ts` | Beat、WordTimestamp、alignment 类型 |
| `NarrativeReviewPanel.tsx` | beat 展示、编辑和 dirty 状态 |
| `src/hooks/useNarrative.ts` | TTS 请求/响应 beats |
| 风格库相关页面 | 展示/创建新的推荐内置组件，无新增 category |

---

## 17. 测试方案

### 17.1 单元测试

`test_volcengine_tts.py`：

- 收集多 chunk 音频；
- 收集多个 sentence.words；
- 重复 metadata 去重；
- 时间排序、裁剪；
- 无 sentence 字段时兼容。

`test_beat_aligner.py`：

- 中文逐字完全匹配；
- `"好，"`等多字符 token；
- 空格、换行、全半角标点；
- narration 中重复短语；
- 部分 timestamp 缺失；
- 部分 beat 插值；
- 无 timestamp 字数回退；
- 最后 beat 覆盖 scene 尾部；
- 时间不越界且单调。

`test_narrative_provider.py`：

- 固定 prompt 包含 beat 契约；
- 可变 prompt 出现在正确位置；
- 引擎技术词不进入 narrative style 示例；
- 输出 beats 被校验；
- narrative 响应缺失 beats 时校验失败并触发修复/任务重试。

`test_code_provider.py`：

- code prompt 包含 resolved beat 时间；
- 不包含 word timestamps；
- failed alignment 使用回退规则；
- Manim/Remotion 各自时间规则存在。

### 17.2 Worker/API 测试

- NarrativeWorker 保存音频、timestamps、resolved beats；
- 修改 cue 后重新 TTS 和 alignment；
- 只修改 visual action 不触发 TTS；
- 审核创建新 NarrativeVersion 时保留 beats；
- CodeWorker 保存 beats 和 code；
- 缺失 beats、beat 索引断裂或 cue 覆盖不足时不会进入代码生成。

### 17.3 集成验收

同一选题分别使用 Manim 和 Remotion 生成：

1. 含 3～4 beats 的 12 秒机制镜头；
2. 数字揭晓镜头；
3. 人数增加并责任分裂镜头；
4. 错误/正确行动对比镜头。

人工检查：

- 动画与对应关键词误差主观不超过约 300ms；
- 不在镜头开头一次性完成全部动作；
- 不出现超过 3 秒且没有语义需要的静止画面；
- 最终动画总时长不超过音频；
- 两个引擎表达相同 beat 语义。

---

## 18. 发布与回滚

### 阶段 1：TTS 时间戳旁路采集

- 只解析和保存 timestamps；
- 不改变 prompt 和代码生成；
- 验证生产响应格式、重复规则和覆盖率。

### 阶段 2：Narrative beats

- 新 narrative 输出 beats；
- TTS 后执行 alignment；
- 审核页先只读展示 beats；
- 未满足 beats 契约的 narrative 不允许通过审核。

### 阶段 3：代码生成消费 beats

- Manim/Remotion prompt 开启时间执行规则；
- 小流量生成对比；
- 监控截断率、代码修复率、渲染失败率。

### 阶段 4：编辑能力与默认启用

- 审核页开放 beat 编辑；
- 新推荐 prompt components 设为内置可选项；
- 质量稳定后默认启用。

回滚采用代码版本回滚，不在运行时代码中维护无 beats 分支。由于项目处于开发初期，回滚期间产生的开发数据可清理后重新生成。

---

## 19. 工程量评估

| 模块 | 预估 |
|---|---:|
| Schema、Narrative 契约与校验 | 1～1.5 人日 |
| 火山时间戳解析与 BeatAligner | 1.5～2 人日 |
| Code prompt 与双引擎规则 | 1～1.5 人日 |
| 审核 API 与前端 beat 编辑 | 1.5～2 人日 |
| Prompt snapshot 与迁移 | 0.5～1 人日 |
| 测试、双引擎调优与回归 | 1.5～2 人日 |
| **合计** | **7～10 人日** |

如果第一阶段不做 prompt snapshot 和前端 beat 编辑，仅完成后端生成、对齐和代码消费，可在约 4～6 人日内完成可验证版本。

---

## 20. 验收标准

功能验收：

- 新 scene 默认包含合法 beats；
- cue 对 narration 覆盖率达到 95% 以上；
- 火山 timestamp 正常响应时，scene alignment coverage 达到 95% 以上；
- TTS 修改后 beats timing 会重新计算；
- 缺失 beats 的 scene 会被明确拒绝，不进入代码生成；
- Manim/Remotion render API 无破坏性变更；
- 部署异常时可以通过代码版本回滚恢复。

质量验收：

- 普通镜头每 2～4 秒至少有一个有意义的视觉变化；
- 主要视觉结果与对应语音关键词基本同步；
- 动画不是集中在 scene 开头；
- 不依赖重复双圆、光晕和统一居中构图生成全部内容；
- 视频总时长符合平台 pacing 组件约束；
- 同一内容版本可定位实际使用的基础 prompt 版本、引擎规范和平台组件文本。
