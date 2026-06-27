# Sprint 3 设计文档：视频生成 + 视频审核

## 概述

Sprint 3 实现视频生产流水线的第二阶段：在 Sprint 2 完成脚本审核（闸门①）之后，将审核通过的 `ScriptVersion` 转化为最终视频。核心流程是：并发 TTS 合成 → Manim 渲染 → 视频上传 MinIO → 用户审核（闸门②）。

## 整体数据流

```
RenderWorker._execute(task)
  ├─ 读 ScriptVersion（scenes + render_engine）
  ├─ 读 project.tts_voice → 查 VOICE_ALIAS_MAP → 火山 speaker ID
  ├─ asyncio.gather（并发）→ [VolcengineTTSEngine.synthesize(scene_i) for each scene]
  │     每个 scene mp3 上传 MinIO: audio/{project_id}/{script_version_id}/scene_{index}.mp3
  ├─ 生成 Manim Python 脚本（含各 scene 音频路径注入）
  ├─ asyncio.create_subprocess_exec("python -m manim ...")
  │     超时 10 分钟，捕获 stdout/stderr → render_log
  ├─ 输出视频上传 MinIO: video/{project_id}/{script_version_id}/{asset_id}.mp4
  ├─ 写 VideoAsset（video_file_key, duration_seconds, status="ready"）
  └─ 更新 project.current_video_asset_id，signal render_completed
```

## 新增文件

```
backend/app/engines/tts/
  volcengine.py       火山引擎 HTTP 实现（VolcengineTTSEngine）
  factory.py          get_tts_engine() 工厂
  voice_map.py        别名 → speaker ID 映射表

backend/app/engines/render/
  manim.py            ManimRenderEngine（subprocess 实现）
  factory.py          get_render_engine() 工厂

backend/app/workers/
  render_worker.py    填充 _execute()（现为 NotImplementedError）

backend/app/api/
  projects.py         新增 GET /api/projects/{id}/video-url?asset_id=<uuid>
```

修改文件：
- `backend/app/config.py`：新增 TTS 配置字段
- `backend/.env.example`：新增 TTS 环境变量示例

## 火山引擎 TTS 实现

### 配置（config.py 新增）

```python
VOLCENGINE_TTS_API_KEY: str = ""
VOLCENGINE_TTS_RESOURCE_ID: str = "seed-tts-2.0"
TTS_ENGINE: str = "volcengine"
```

### 音色别名映射（voice_map.py）

```python
VOICE_ALIAS_MAP = {
    "male_calm":    "<实际火山 speaker ID>",
    "female_warm":  "<实际火山 speaker ID>",
    # 按需扩展
}
```

- 前端创建项目时传 `tts_voice="male_calm"`（别名）
- RenderWorker 渲染前查 `VOICE_ALIAS_MAP`；别名不存在则 fallback 到原值（允许直接传 speaker ID）

### HTTP 调用规范

接口：`POST https://openspeech.bytedance.com/api/v3/tts/unidirectional`

必选请求头：
- `X-Api-Key`：`VOLCENGINE_TTS_API_KEY`
- `X-Api-Resource-Id`：`VOLCENGINE_TTS_RESOURCE_ID`
- `X-Api-Request-Id`：每次调用生成的 UUID

请求体关键字段：
```json
{
  "req_params": {
    "text": "<scene.narration>",
    "speaker": "<resolved speaker ID>",
    "audio_params": {
      "format": "mp3",
      "sample_rate": 24000
    }
  }
}
```

响应：`data` 字段为 base64 编码音频，decode 后写入临时文件再上传 MinIO。

## Manim 渲染实现

### 执行方式

使用 `asyncio.create_subprocess_exec` 调用：
```
python -m manim render <script_file> <SceneName> --output_file <output_path> ...
```

- Worker 持有 subprocess 引用，设置 10 分钟超时
- 超时后调用 `proc.terminate()`，作为失败处理
- stdout + stderr 合并为 `render_log` 存入 `VideoAsset`

### 音频注入

整个脚本是**一个 Manim Scene**，所有镜头代码共享同一个 `construct()` 作用域。RenderWorker 在生成 Manim 脚本时，在每个镜头动画块的起始处插入 `self.add_sound("<audio_path>")`，对应该镜头的 TTS 音频（已下载到本地临时目录）。注入顺序与 `scenes[]` 数组顺序一致。

## MinIO 存储路径

| 类型 | 路径 |
|------|------|
| 场景音频 | `audio/{project_id}/{script_version_id}/scene_{index}.mp3` |
| 最终视频 | `video/{project_id}/{script_version_id}/{asset_id}.mp4` |

`script_version_id` 标识产物来源脚本版本，`asset_id` 保证同一脚本多次渲染不冲突。

## 视频审核 API

```
GET /api/projects/{id}/video-url?asset_id=<uuid>
Response: { "url": "<presigned_url>", "expires_in": 3600 }
```

- 后端验证 `asset.project_id == project.id`，防止跨项目访问
- 不限制 project.status，支持查看任意历史版本视频
- presigned URL 有效期 1 小时

前端在 `video_review` 状态下以及历史时间线上均可调用此端点，直接用 `<video src>` 播放。

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| 任意 scene TTS 失败 | `gather(return_exceptions=True)` 收集后统一检查，任一失败则整体失败 |
| Manim 非零退出 | 写 `VideoAsset.status="failed"`，render_log 记录 stderr，signal `render_completed(success=False)` |
| MinIO 上传失败 | 抛异常，由 BaseWorker 统一捕获走重试 |
| Manim 超时（>10分钟） | terminate 子进程，作为失败处理 |
| 音色别名不存在 | fallback 到原值，不报错 |

失败后 Workflow 的重试逻辑由现有 `check_and_increment_retry` activity 处理，无需 RenderWorker 额外关心。

## VideoAsset 状态

`VideoAsset.status` 需支持以下值：
- `rendering`（默认，已有）
- `ready`（渲染成功）
- `failed`（渲染失败）

## 不在本 Sprint 范围内

- Manim 代码验证（`RenderEngine.validate_code`）：保留接口，实现留空
- TTS stub 实现（仅实现 volcengine，无需 stub）
- 视频剪辑、字幕生成
