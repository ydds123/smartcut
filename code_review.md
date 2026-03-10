# SmartCut 代码审查报告

**审查时间**: 2026-02-23 | **代码规模**: ~12,600 行 | **阶段**: MVP

---

## 🔴 高风险（3 项）

### H1 — 文件类型仅靠 MIME 校验，可被绕过
**位置**: `backend/app/services/file_service.py:84-92`

```python
# 当前：只检查 HTTP header 中的 content_type（客户端可伪造）
return file.content_type in valid_mime_types
```

攻击者可以将任意文件（如脚本）的 `Content-Type` 设为 `video/mp4` 绕过校验。**应加 magic bytes 检测**（读取文件头部字节验证真实格式）。

---

### H2 — 整个 API 无认证机制
**位置**: `backend/app/main.py`、`backend/app/api/tasks.py`

所有接口（上传、处理、删除、获取结果）无需任何 token 或认证即可访问。本地工具可接受，但若未来暴露到局域网或公网，任何人都能操作你的任务和文件。

---

### H3 — FFmpeg 子进程 `process.wait()` 无超时
**位置**: `backend/app/services/video_processor.py:1028`

```python
return_code = process.wait()  # ← 无 timeout 参数，可能永久挂起
```

如果 FFmpeg 因某种原因卡死，Worker 进程会永久阻塞。RQ 的 `job_timeout=600` 只能终止 RQ job，不会 kill 子进程。**应改为 `process.wait(timeout=xxx)` 并在超时时调用 `process.kill()`**。

---

## 🟡 中风险（8 项）

### M1 — Redis 连接在模块导入时创建，无重试
**位置**: `backend/app/api/tasks.py:30-31`

```python
redis_conn = Redis.from_url(settings.REDIS_URL)  # 模块级，启动时 Redis 不可用则崩溃
queue = Queue(connection=redis_conn)
```

Redis 不可用时整个 API 模块无法导入，应用直接崩溃。应改为懒加载或加连接重试。

---

### M2 — `save_review_data` 接受任意 JSON，无 schema 校验
**位置**: `backend/app/api/tasks.py:347-366`

```python
body: dict = Body(...)  # 无类型约束
scenes = body.get("scenes")
if not isinstance(scenes, list):  # 只检查是否为 list，不验证内容
    raise HTTPException(...)
```

`scenes` 内的每个对象没有验证 `start_ms`/`end_ms` 是否存在、是否为整数、是否合理。恶意数据可能导致后续切分崩溃。

---

### M3 — `ffprobe` 调用无超时，可能挂起
**位置**: `backend/app/services/video_processor.py:1330`, `1348`

`_get_video_duration_ms()` 和 `_get_video_fps()` 中的 `subprocess.run()` 均无 `timeout` 参数。损坏的视频文件可能导致 ffprobe 挂起，进而阻塞整个 Worker。

---

### M4 — 静态文件目录完全公开，无访问控制
**位置**: `backend/app/main.py:36`

```python
app.mount("/data", StaticFiles(directory=data_dir), name="data")
```

`/data` 下的所有文件（上传视频、切分片段、缩略图）对任何能访问服务器的人完全公开，无需认证。

---

### M5 — 前端无条件每 5 秒轮询，即使无活跃任务
**位置**: `frontend/src/hooks/useTasks.ts:17`

```typescript
refetchInterval: 5000,  // 所有任务完成后仍持续轮询
```

当所有任务都处于终态（COMPLETED/FAILED）时，轮询毫无意义但持续消耗资源。应在无活跃任务时暂停轮询。

---

### M6 — 单场景切分失败导致整个任务失败
**位置**: `backend/app/workers/video_tasks.py:217-220`

`split_video()` 遇到失败场景会静默跳过（`continue`），但上层严格校验 `len(output_files) != len(final_scenes)` 时抛出异常。这意味着 100 个场景中任意 1 个失败，整个任务就失败。对于长视频来说过于严格。

---

### M7 — 无全局 React Error Boundary
**位置**: `frontend/src/App.tsx`

`App.tsx` 只处理了 `useTasks` 的 `error` 状态，但没有 React Error Boundary 包裹整个应用。任何子组件的运行时错误（如 `ReviewModal`、`TimelineModal`）都会导致整个应用白屏。

---

### M8 — `Math.random()` 用于 Toast ID 生成
**位置**: `frontend/src/stores/uiStore.ts:97`

```typescript
const id = Math.random().toString(36).substring(7)  // 非密码学安全，有碰撞风险
```

快速连续触发多个 Toast 时可能产生重复 ID，导致 Toast 无法正确移除。应改用 `crypto.randomUUID()`。

---

## 🟢 低风险（6 项）

| # | 位置 | 问题 |
|---|------|------|
| L1 | `models.py:31-32` | `datetime.utcnow()` 已在 Python 3.12 弃用，应改为 `datetime.now(timezone.utc)` |
| L2 | `models.py:48-56` | `ErrorLog` 模型定义但从未使用，是死代码 |
| L3 | `video_tasks.py:299` | `review_notes` 字段被用来存储异常信息，语义混用 |
| L4 | `video_processor.py:1296-1305` | `_timecode_to_ms()` 无错误处理，格式异常会抛出未捕获的 `IndexError` |
| L5 | `config.py:7` | SQLite 并发写入有限制，MVP 可接受，扩展时需替换 PostgreSQL |
| L6 | `main.py` / `tasks.py` | 无速率限制，上传和处理接口可被滥用 |

---

## 优先级建议

**立即处理**（影响稳定性）:
- H3 — FFmpeg 无超时 → 加 `process.wait(timeout=600)` + `process.kill()`
- M3 — ffprobe 无超时 → 同上，加 `timeout=30`
- M6 — 单场景失败策略 → 改为允许部分成功

**近期处理**（影响安全性）:
- H1 — 加 magic bytes 校验
- M2 — 用 Pydantic schema 替换 `body: dict`
- M7 — 加全局 Error Boundary

**有空处理**（代码质量）:
- M5 — 智能轮询（检测活跃任务状态）
- M8 — `crypto.randomUUID()`
- L1-L6 — 清理死代码、修复弃用 API
