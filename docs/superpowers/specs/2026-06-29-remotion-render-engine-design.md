# Remotion 渲染引擎设计文档

## 概述

在已有 `ManimRenderEngine` 的基础上，新增 `RemotionRenderEngine`，将 AI 生成的 JSX 代码片段组合为完整 Remotion 视频。渲染方式与 Manim 平行：Python 生成完整组合文件 → subprocess 调用 Remotion CLI → 上传视频。

## 目录变动

```
remotion-template/              ← 新增，提交到 git
  package.json
  tsconfig.json
  remotion.config.ts
  src/
    index.tsx                   ← 固定，registerRoot(Root)
    Root.tsx                    ← 固定，Composition + calculateMetadata
    VideoScene.tsx              ← 占位文件（运行时被 Python 覆写到 tmpdir）

backend/app/engines/render/
  remotion.py                   ← 新增，RemotionRenderEngine

backend/app/config.py           ← 新增 REMOTION_TIMEOUT_SECONDS、REMOTION_TEMPLATE_DIR
backend/app/engines/render/factory.py  ← 加 remotion 分支
backend/app/workers/render_worker.py   ← 日志 hardcode "Manim" 改为动态 engine 名
```

## remotion-template 模板结构

### package.json 关键依赖

```json
{
  "dependencies": {
    "react": "^18",
    "react-dom": "^18",
    "remotion": "^4"
  },
  "devDependencies": {
    "@remotion/cli": "^4",
    "typescript": "^5"
  }
}
```

依赖用 pnpm 预装，`node_modules` 随 Docker 镜像打包（不提交到 git，`.gitignore` 排除）。

### src/index.tsx（固定）

```tsx
import { registerRoot } from 'remotion';
import { Root } from './Root';
registerRoot(Root);
```

### src/Root.tsx（固定）

```tsx
import { Composition } from 'remotion';
import { VideoScene, totalFrames } from './VideoScene';

export const Root = () => (
  <Composition
    id="VideoScene"
    component={VideoScene}
    durationInFrames={totalFrames}
    fps={30}
    width={1280}
    height={720}
  />
);
```

`totalFrames` 从生成的 `VideoScene.tsx` 导入，`Root.tsx` 无需改动即可适配任意时长。

### src/VideoScene.tsx（占位，运行时覆写）

占位文件仅用于让模板本身可以通过 TypeScript 检查；实际渲染时 Python 在 tmpdir 内写入真实内容。

## 生成的 VideoScene.tsx 结构

Python 按以下模式生成：

```tsx
import React from 'react';
import { AbsoluteFill, Sequence, Audio, useCurrentFrame,
         useVideoConfig, interpolate, spring } from 'remotion';

export const totalFrames = <所有镜头 durationInFrames 之和>;

export const VideoScene: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={180}>
      <Audio src="file:///tmp/xyz/scene_0_audio.mp3" />
      <>
        {/* scene 0 AI-generated JSX — 直接嵌入，不额外包装 */}
        const frame = useCurrentFrame();
        ...
      </>
    </Sequence>
    <Sequence from={180} durationInFrames={150}>
      <Audio src="file:///tmp/xyz/scene_1_audio.mp3" />
      <>...</>
    </Sequence>
  </AbsoluteFill>
);
```

**时长计算规则：**
- 有音频：`durationInFrames = round(scene.audio.duration_seconds * fps)`
- 无音频：`durationInFrames = round(scene.estimated_duration_seconds * fps)`，estimated_duration_seconds 从 ScriptVersion scenes 数据中读取（若缺失则 fallback 5 秒）
- `from` = 前序所有镜头 durationInFrames 之和（累加）

**AI 生成代码的嵌入方式：** scene.code 已是合法 JSX 片段（含 `useCurrentFrame()` 等 hooks），直接插入 `<Sequence>` 内部，作为该 Sequence 的 render function body 或子组件。Python 将每个 scene 的代码包装为一个内联箭头函数组件以隔离 hooks 作用域：

```tsx
{(() => {
  // AI generated code for scene N
  ...
  return (...JSX...);
})()}
```

## RemotionRenderEngine 实现

### render() 流程

```
1. 从 settings.REMOTION_TEMPLATE_DIR 确定模板路径（相对于项目根目录）
2. 在 tmpdir 内：
   a. 复制模板文件：package.json / tsconfig.json / remotion.config.ts
   b. mkdir src/，复制 src/index.tsx、src/Root.tsx
   c. os.symlink(template_node_modules, tmpdir/node_modules)
   d. 生成 src/VideoScene.tsx（_build_remotion_scene() 函数）
3. 运行：
   node_modules/.bin/remotion render VideoScene output.mp4 --fps 30
   工作目录 = tmpdir
4. 捕获 stdout+stderr → render_log，超时 REMOTION_TIMEOUT_SECONDS（默认 600s）
5. 超时 → kill proc → 返回失败 RenderResult
6. returncode != 0 → 返回失败 RenderResult
7. _find_output_video(tmpdir) 找到 mp4 → 读取 bytes
8. 返回 _RenderResultWithBytes（与 Manim 引擎相同的子类）
```

### health_check()

```python
async def health_check(self) -> bool:
    # 检查 node_modules/.bin/remotion 可执行文件是否存在
    remotion_bin = Path(settings.REMOTION_TEMPLATE_DIR) / "node_modules/.bin/remotion"
    return remotion_bin.exists()
```

### 配置（config.py 新增）

```python
REMOTION_TIMEOUT_SECONDS: int = 600
REMOTION_TEMPLATE_DIR: str = "remotion-template"  # 相对于项目根目录
```

## 工厂改动（factory.py）

```python
from app.engines.render.manim import ManimRenderEngine
from app.engines.render.remotion import RemotionRenderEngine

def get_render_engine(engine_name: str = "manim"):
    if engine_name == "manim":
        return ManimRenderEngine()
    if engine_name == "remotion":
        return RemotionRenderEngine()
    raise ValueError(f"Unknown render engine: {engine_name}")
```

## RenderWorker 改动

仅将日志中 hardcode 的 `"Manim"` 字符串改为使用 `render_engine_name` 变量，使日志准确反映实际引擎。

## 错误处理

| 场景 | 处理方式 |
|------|---------|
| node_modules 不存在（未预装） | render() 开始前检查 bin 路径，直接返回失败 RenderResult，错误信息提示需运行 pnpm install |
| Remotion 非零退出 | 返回失败 RenderResult，render_log 含 stderr |
| 超时（>600s） | kill proc，返回失败 RenderResult |
| AI 生成代码含语法错误 | Remotion bundle 阶段报错，体现在 render_log，正常走失败路径 |
| symlink 已存在（tmpdir 复用时） | 用 `os.symlink` 前先检查，已存在则跳过 |

## 不在本次范围

- `validate_code()`：接口保留，实现留空（返回 `True, ""`），与 Manim 保持一致
- Remotion Studio / 预览功能
- 字幕、水印等后处理
