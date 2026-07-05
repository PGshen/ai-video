# 卡死阶段重置功能设计

## 背景

Temporal workflow (`VideoProductionWorkflow`) 在三个自动化阶段会阻塞等待 worker 完成任务后发来的信号：

| project.status       | 提交的任务 (task_type)  | 等待的信号            |
|----------------------|--------------------------|-----------------------|
| `narrative_generating` | `generate_narrative`   | `narrative_generated` |
| `code_generating`      | `generate_code`        | `code_generated`      |
| `video_generating`     | `render_video`         | `render_completed`    |

`BaseWorker._claim_next_task` 用 `UPDATE ... FOR UPDATE SKIP LOCKED` 把 `worker_tasks` 行从 `pending` 置为 `processing`。如果 worker 进程在这之后崩溃（OOM/SIGKILL/意外退出），该行永久停留在 `processing`，不会有任何信号发给 workflow，`wait_condition` 永久阻塞，`video_projects.status` 卡在上述三个状态之一。当前代码库没有心跳、租约超时或巡检机制。

## 目标

新增一个手动触发的运维/管理 API 接口，让操作者在确认某个 project 卡死在上述三个阶段之一时，可以将其重置，使其恢复正常执行，而无需重启 workflow 或手工改数据库。

## 非目标

- 不做自动巡检 / 心跳检测卡死任务（用户已选择纯手动触发）。
- 不修改 `project.retry_count`（该字段用于自动失败重试计数，与运维重置是两回事）。
- 不修改 `VideoProductionWorkflow` 的定义或信号处理逻辑。
- 不处理人工审核闸门（`narrative_review`/`script_review`/`video_review`）卡死的场景——这些不是本次范围。

## 设计

### 核心思路

不直接向运行中的 workflow 发送信号。而是复用现有的 `submit_narrative_task` / `submit_code_task` / `submit_video_generation_task`（`app/workflows/activities.py`）——这些函数本质上是普通的异步函数，只是恰好被 Temporal worker 通过 `execute_activity` 调用。API 层可以直接 `await` 调用它们，插入一条新的 `WorkerTask` 记录。

workflow 仍然阻塞在原来的 `wait_condition(...)` 上；一旦新任务被某个 worker 认领并完成，worker 会按现有逻辑（`BaseWorker._send_signal`）发出 `narrative_generated`/`code_generated`/`render_completed` 信号，`wait_condition` 自然满足，workflow 恢复执行。**因此重置逻辑完全不需要触碰 workflow 代码或 Temporal 信号 API。**

### 竞态问题与处理

重置的前提是操作者判断某任务已经卡死，但无法从数据库层面 100% 排除"旧 worker 其实还活着，只是很慢"的可能。如果旧 worker 之后真的完成了任务，会再发一次同名信号；这个多余信号会被 workflow 存进 `self._signals[name]` 列表，在未来某次同名 `_wait_signal` 调用时被错误地当作"本次"结果消费掉（时序错位，可能导致虚假成功或吞掉真实错误）。

处理方式：

1. `WorkerTask.status` 新增取值 `"cancelled"`（该列是自由 `String(20)`，无需数据库迁移）。
2. 重置时，把该 project + task_type 下所有处于 `pending`/`processing` 的 `WorkerTask` 行标记为 `cancelled`。
3. 修改 `BaseWorker._process_task`：在成功或失败分支写回最终状态、发信号之前，重新从数据库读取该任务行的当前 `status`；如果已经是 `cancelled`，跳过状态写回和 `_send_signal`，只记录日志后返回。

这样旧 worker 即使"复活"完成了任务，也不会向 workflow 发出多余信号。

### 新增内容

**`app/workflows/activities.py`** — 新增 `reset_stuck_stage(project_id: str) -> dict`：

- 加载 project；根据 `project.status` 映射到 `task_type`：
  - `narrative_generating` → `generate_narrative`
  - `code_generating` → `generate_code`
  - `video_generating` → `render_video`
  - 其他状态 → 抛 `ValueError`（由 API 层转换成 400）
- 查询该 project_id + task_type 下 `status in ('pending', 'processing')` 的 `WorkerTask` 行，全部置为 `cancelled`，收集其 id 列表。
- 直接 `await` 调用对应的 `submit_narrative_task` / `submit_code_task` / `submit_video_generation_task(project_id)`，生成一条新的 `WorkerTask`。
- 写入一条 `ProjectEvent`（`event_type="stuck_reset"`，`payload={"stage": task_type, "cancelled_task_ids": [...]}`），便于时间线审计。
- 返回 `{"stage": task_type, "cancelled_task_ids": [...], "new_task_id": ...}`。

这个函数不通过 `workflow.execute_activity` 调用，不需要 Temporal 上下文，纯粹作为数据库操作 + 复用现有 submit 函数被 API 层直接调用。

**`app/api/`** — 新增端点 `POST /api/projects/{project_id}/reset`：

- 依赖：`Depends(get_async_session)` + `Depends(verify_api_key)`（不需要 `get_temporal_client`，因为不发 Temporal 信号）。
- 无请求体：直接从当前 `project.status` 推断要重置的阶段。
- 校验 project 存在；`project.status` 不属于三个可重置状态之一时返回 400。
- 调用 `reset_stuck_stage`，返回 `{"status": "reset", "project_id": ..., "stage": ..., "cancelled_task_count": ...}`。

**`app/workers/base.py`** — `_process_task` 增加 cancelled 校验（见上文"竞态问题与处理"）。

**`app/models/worker_task.py`** — 无 schema 改动，只是文档/注释里补充 `status` 的合法取值包含 `cancelled`。

### 测试计划

- 单元测试 `reset_stuck_stage`：三种阶段各构造一条 `processing` 的 `WorkerTask`，调用后验证旧行变 `cancelled`、生成新行、`ProjectEvent` 写入。
- 单元测试非法状态（如 `script_review`）调用 `reset_stuck_stage` 抛错。
- `BaseWorker` 测试：模拟一个任务在执行期间被外部标记为 `cancelled`，验证 `_process_task` 不写回 `completed`/`failed` 状态、不调用 `_send_signal`。
- API 测试：正常重置 200，非法阶段 400，project 不存在 404。

## 影响范围

- 新增文件：无（改动集中在 `activities.py`、`base.py`、新增/复用 API router）。
- 数据库：无迁移，`worker_tasks.status` 新增字符串取值属于应用层约定。
- 不影响现有 workflow 定义与已运行的 workflow 实例。
