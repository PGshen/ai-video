# 音画同步设计文档

**日期**：2026-06-28  
**状态**：已批准

## 问题

渲染视频时存在音画不同步：上一镜头音频未结束就切到下一镜头动画，或音频结束后动画仍在播放。根本原因是 TTS 音频在渲染阶段才生成，CodeWorker 生成 Manim 代码时没有音频时长信息，无法约束动画时长。

## 方案

将 TTS 音频生成提前到叙事生成之后，把音频元数据（`audio_key`、`duration_seconds`）存入 `NarrativeVersion.scenes`，在叙事审核阶段让用户试听并可重新生成，最后 CodeWorker 读取时长注入 prompt 约束 Manim 动画，RenderWorker 直接复用已有音频不再重新 TTS。

## 数据结构

`NarrativeVersion.scenes` JSONB 数组中每个镜头对象新增三个字段：

```json
{
  "scene_index": 0,
  "narration": "...",
  "description": "...",
  "audio_key": "audio/{project_id}/{narrative_version_id}/scene_0.mp3",
  "duration_seconds": 12.4,
  "tts_status": "ready"
}
```

`tts_status` 枚举值：`pending` | `ready` | `failed`

无需数据库 migration，仅扩展 JSONB 字段约定。

## 后端变更

### NarrativeWorker

叙事生成并保存 `NarrativeVersion` 后，立即在 worker 内并发合成所有镜头 TTS（并发数 ≤ 3，与现有 RenderWorker 的 Semaphore 约束一致），将结果写回 `scenes`，再 commit，最后才发出 `narrative_generated` signal。

流程：
```
generate_narrative
→ save NarrativeVersion (scenes.tts_status = "pending")
→ 并发 TTS（Semaphore(3)）
→ 更新 scenes[i].audio_key / duration_seconds / tts_status
→ commit
→ signal narrative_generated
```

TTS 失败的镜头：`tts_status = "failed"`，`duration_seconds = null`。不阻断整体流程，但 CodeWorker 和前端需要处理 null 的情况。

### 新增 API：单镜头重新 TTS

```
POST /api/projects/{project_id}/narrative/tts
Body: { "scene_index": int, "narration": str }
Response: { "audio_key": str, "duration_seconds": float, "tts_status": str }
```

逻辑：合成后更新 `current_narrative_version_id` 对应的 `NarrativeVersion.scenes[scene_index]` 并返回新字段。供前端用户修改旁白后重新生成单个镜头音频。

### CodeWorker / AI Prompt

在 system prompt 里追加全局约束（现有 scenes JSON 结构不变，`duration_seconds` 字段已在每个镜头对象中）：

```
每个镜头 JSON 包含 duration_seconds 字段，代表该镜头旁白音频的时长（秒）。
生成的 Manim 代码中，该镜头所有动画的总时长（所有 Animation 的 run_time 与 self.wait 之和）
必须 ≤ duration_seconds。建议最后用 self.wait() 补足剩余时间，使动画与音频完全对齐。
```

`duration_seconds` 为 null 的镜头（TTS 失败）：prompt 中不加约束，AI 自行估算。

### RenderWorker

- 从 `NarrativeVersion.scenes[i].audio_key` 直接下载音频，**不再调用 TTS**
- `SceneAudio.duration_seconds` 从 `scenes[i].duration_seconds` 读取（不再写死 `0.0`）
- 删除 TTS 相关逻辑（`tts_engine`、`tts_requests`、上传音频步骤）

## 前端变更

### 叙事审核页面（`narrative_review` 状态）

每个镜头卡片在旁白文本框下方新增：

1. **音频播放器**：HTML `<audio>` 标签，`src` 指向 `audio_key` 的 presigned URL 或代理接口，显示时长
2. **时长标注**：`旁白时长：12.4s`（来自 `duration_seconds`）
3. **重新生成按钮**：用户修改旁白后出现，调用 `POST .../narrative/tts`，期间 loading，完成后刷新播放器和时长

**提交阻断**：若存在 `tts_status !== "ready"` 的镜头（修改了旁白但未重新生成），阻断提交并提示。

**审核提交**：逻辑不变，仍走 `POST /api/projects/{project_id}/review`（`gate: narrative`），`edited_scenes` 包含最新的 scenes（含新 `audio_key` 和 `duration_seconds`）。

## 接口变更汇总

| 变更 | 类型 |
|------|------|
| `NarrativeWorker`：生成后立即 TTS 并写回 scenes | 修改 |
| `RenderWorker`：移除 TTS 逻辑，从 scenes 读 audio_key | 修改 |
| CodeWorker system prompt：追加 duration_seconds 约束 | 修改 |
| `POST /api/projects/{project_id}/narrative/tts` | 新增 |
| 前端叙事审核页：音频播放器 + 重新生成按钮 | 修改 |

## 边界情况

- **TTS 失败**：`tts_status=failed`，前端显示「生成失败，请重试」，提交前必须修复
- **旁白为空**：跳过 TTS，`duration_seconds=null`，CodeWorker prompt 不约束该镜头
- **用户修改旁白后直接提交**：提交时前端检查 tts_status，阻断并提示重新生成
