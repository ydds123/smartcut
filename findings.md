# Findings - SmartCut

## 根因
- 用户侧 `Network Error` 主要由后端不可达触发。
- 地址层面存在 `localhost` / `127.0.0.1` 混用；`localhost` 在部分运行时优先解析 `::1`，与仅 IPv4 监听的后端不兼容。

## 代码层修复
- 前端 API 默认地址改为 `http://127.0.0.1:8000`。
- Vite `/api` 与 `/upload` 代理目标改为 `http://127.0.0.1:8000`。
- 前端 `.env.local` / `.env.example` 改为 `127.0.0.1`。
- 时间轴缩略图 URL 不再硬编码 `localhost`，改用 `VITE_API_URL`。
- 后端 CORS 加入 `http://127.0.0.1:5173`。
- 后端 `run.sh` 固定优先 `.venv` 解释器，并默认绑定 `127.0.0.1:8000`。

## 验证结果
- TypeScript 编译通过：`npx tsc --noEmit`。
- 联通性检查通过：`localhost:5173/api/tasks` 返回 200（后端运行时）。
- 无头 E2E（指定视频）通过：
  - task_id: `5b07d821-e075-4067-917d-23277056c35d`
  - status: `COMPLETED`
  - progress: `100`
  - total_scenes: `57`
  - created_at: `2026-02-19T09:03:41.915905`
  - updated_at: `2026-02-19T09:04:52.585939`

## 稳定性增强（跨平台）
- 新增 `tools/devstack.py`，支持 Windows/macOS 统一命令管理三服务。
- 新增包装脚本：
  - `tools/devstack.sh`（macOS）
  - `tools/devstack.ps1`（Windows）
- 新增配置：
  - `tools/devstack_config.json`
- 能力：
  - 自动拉起 backend/frontend/worker
  - 自动重启 + 限频熔断
  - `doctor` 环境体检
  - `status/ps/logs/restart/down` 运维命令
  - `restart <service>`（如 `restart backend`）支持定向单服务重启

## 2026-02-20 TransNet 接入修复结论
- 旧版 `transnet_architecture.py` 为自定义网络，和官方权重结构不一致，导致推理时出现线性层维度错误。
- 本地模型文件 `~/.smartcut/models/transnetv2-pytorch-weights.pth` 仅 `122071 bytes`，远小于可用模型体积，且权重键数量极少，不是可用 checkpoint。
- 已将推理路径改为官方 PyTorch 架构兼容输入：`[B, T, 27, 48, 3] uint8`。
- 已加入模型有效性校验：
  - 文件大小下限 `5MB`
  - 状态字典键数量下限 `120`
  - 必需关键键存在性检查
  - 加载覆盖率检查（<95% 直接拒绝）
- 新行为：无效权重时直接标记 `transnet_model_unavailable` 并回退 PySceneDetect，不再触发 shape 报错。
- 烟测任务：`ac6c8269-fe11-41a1-b615-12fcfe55d7e3`（2026-02-20）
  - `status=COMPLETED`
  - `detection_report.fallback_reason=transnet_model_unavailable`
  - 回退稳定，任务不中断。

## 2026-02-20 官方权重获取阻塞与替代落地
- 直接执行官方流程时，`git lfs pull` 失败：`This repository exceeded its LFS budget`，无法从官方仓库拉取 `inference/transnetv2-weights` 实体文件。
- 本机已安装 `git-lfs`，确认阻塞属于上游仓库配额，不是本地配置问题。
- 采用可执行替代：从 PyPI `transnetv2-pytorch==1.0.5` 提取 `transnetv2-pytorch-weights.pth`。
- 新权重文件大小：`30,506,391 bytes`，state_dict key 数：`90`，与当前官方兼容架构 100% 匹配。
- 调整校验阈值后（`MIN_EXPECTED_STATE_KEYS=80`），`TransNetV2Detector.is_available()` 返回 True。
- 精确模式实测成功启用融合：
  - task_id: `75992f4e-56c5-4eaf-adc8-e0c7de9638fa`
  - `fusion_mode=pyscene+transnet`
  - `transnet_applied=true`
  - `fallback_reason=null`
  - `transnet_peak_count=44`

## 2026-02-20 镜头合理性修复（短镜头 + 软过渡）
- 已在 `VideoProcessor.detect_scenes` 增加全局最小时长收敛：默认硬下限 `>= 1000ms`。
- 已在 TransNet 融合阶段增加候选点软评分通道：
  - 对 PyScene 候选帧执行 `score_candidates`（不过阈值过滤）
  - 当候选点未命中强峰时，允许按 `soft_candidate_threshold` 保留
- 已在融合边界后增加按置信度的最小间隔约束，避免过密边界导致 0 秒/极短镜头。
- 回归任务：`6e5ac6d4-5eb8-46c4-b304-005766196aeb`
  - `status=COMPLETED`
  - `fusion_mode=pyscene+transnet`
  - `transnet_applied=true`
  - `min_duration_ms=1209`
  - `<1s 镜头数=0`

## 2026-02-23 代码审阅报告核对结论
- 审阅中“立即处理”项（`H3/M3/M6`）与当前代码完全匹配，属于真实风险：
  - `VideoProcessor.split_video()` 的 `process.wait()` 无超时。
  - `ffprobe` 两处 `subprocess.run()` 无超时。
  - `process_video_task()` 当前要求 `len(output_files)==len(final_scenes)`，会导致单场景失败拖垮整任务。
- 审阅中“近期处理”项里可快速落地的部分：
  - 上传文件类型校验目前仅依赖 MIME，确实可伪造，需要增加 magic bytes 检测。
  - `save_review_data()` 当前仅校验 `scenes` 是 list，缺少子项结构与区间合法性校验。
  - 前端缺少全局 Error Boundary，当前仅有 `TimelineModal` 局部边界。
- 本轮决定优先落地稳定性 + 输入校验 + 前端可用性修复；认证与静态目录访问控制涉及产品策略，先保持兼容不做 breaking 改造。

## 2026-02-23 代码审阅优化落地结果
- `H1` 已修复：`FileService.validate_video_type` 改为 MIME + magic bytes 联合校验，支持 MP4/MOV/AVI/MKV 头部识别并校验 MIME 兼容性。
- `H3` 已修复：`split_video()` 的 FFmpeg 子进程等待改为超时等待并在超时后 kill，避免 worker 永久阻塞。
- `M3` 已修复：`_get_video_duration_ms()` 与 `_get_video_fps()` 的 ffprobe 调用增加超时配置（默认 30s）。
- `M6` 已修复：处理任务与审核切分均支持“部分场景成功”；仅在全部场景失败时任务失败，成功场景会持久化并记录失败统计。
- `M1` 已修复：`api/tasks.py` 改为 Redis/RQ 懒加载 + 重试，避免模块导入阶段因 Redis 不可用导致 API 崩溃。
- `M2` 已修复：新增 `SaveReviewDataRequest` schema，校验 `start_ms/end_ms` 合法区间；接口层增加有序与重叠校验。
- `M5` 已修复：`useTasks` 轮询改为仅在有活跃任务状态时每 5 秒刷新，空闲时停止轮询。
- `M7` 已修复：新增全局 `AppErrorBoundary` 并在 `main.tsx` 包裹 `App`。
- `M8` 已修复：Toast ID 由 `Math.random()` 改为优先 `crypto.randomUUID()`。
- `L1` 已修复：模型默认时间函数改为 `datetime.now(timezone.utc)` 生成的 UTC 时间（兼容现有列格式）。
- `L4` 已修复：`_timecode_to_ms()` 增加格式校验与异常处理，CSV 解析遇到非法时间码会跳过并记录 warning。

## 本轮暂未改动
- `H2/M4/L6`（全局认证、静态目录访问控制、速率限制）仍保留原行为，原因是需要产品级访问模型设计，直接强制改造会产生兼容性破坏。

## 2026-02-23 后续加固落地结果
- 已补齐可开关认证：
  - 后端新增 `require_api_token`，对 `/api/*` 统一生效；
  - 支持 `X-API-Token` Header 与 `api_token` Query（兼容 SSE 与静态资源）。
- 已补齐轻量限流：
  - 新增内存限流器（按 `bucket + client_ip` 计数）；
  - 上传接口与任务写接口接入 429 限流响应。
- 已补齐 `/data` 访问控制：
  - `DATA_PUBLIC_ACCESS=true` 时继续静态公开挂载；
  - `DATA_PUBLIC_ACCESS=false` 时改为受保护文件路由并校验路径合法性。
- 前端已适配：
  - Axios 自动注入 `VITE_API_TOKEN` 到 `X-API-Token`；
  - SSE 连接自动携带 `api_token` 查询参数。
- 文档已补齐：
  - `README.md` 新增认证、限流、数据访问控制配置说明与启用示例。

## 2026-02-23 参数配置统一（PySceneDetect 对齐）
- 现状问题确认：
  - 后端 `quality_tuning.py` 与前端 `ProcessingConfigModal.tsx` 均存在硬编码参数边界，事实源分裂。
  - `downscale=1` 在现有命令构造中不会传递 `--downscale`，语义与“禁用自动降采样”不一致。
  - `frame_skip>0` 与 `--stats` 同时使用会触发 PySceneDetect CLI 约束冲突。
- 已落地修复：
  - 新增 `app/services/processing_param_specs.py` 作为参数规范单源（`default/min/max/step/recommended_range/group/scope/provenance/source_ref`）。
  - `quality_tuning` 改为从参数规范生成默认值与归一化，移除散落 clamp。
  - `tasks` API 新增 `GET /api/config/processing-meta`，并在 `/process`、`/review` 返回中携带 `config_meta`。
  - 前端配置面板改为动态消费后端 `config_meta`，移除硬编码范围与推荐区间。
  - `video_processor` 调整：
    - `downscale>=1` 才显式传递参数，`0` 表示 auto；
    - `frame_skip>0` 时自动禁用 stats 文件，避免 CLI 参数冲突并清理旧 stats。
- 约束分层结论：
  - `pyscenedetect` 参数采用官方约束（如阈值 `0..255`、`fade_bias -100..100`、`downscale 0=auto`）。
  - `smartcut` 扩展参数（TransNet/超时/后处理）保留业务边界并显式标注来源。

## 2026-03-01 并发专项审查（进行中）
- 热点初筛显示以下文件为高风险区域：
  - `backend/app/workers/video_tasks.py`（状态推进、DB 提交节流、任务终态写入）
  - `backend/app/api/tasks.py`（状态跃迁检查 + 队列入队 + 事务边界）
  - `backend/app/api/progress.py`（SSE 轮询/终止条件与 DB 可用性）
  - `backend/app/services/video_processor.py`（FFmpeg/ffprobe 超时与子进程回收）
  - `frontend/src/hooks/useTaskProgress.ts` + `frontend/src/hooks/useTasks.ts`（SSE 与轮询并存下的状态一致性）
- 发现多个重试与超时实现点，但是否“终态冲突/重复入队/状态回退”仍需并行深审确认。

## 2026-03-01 并发专项审查（结论）
- 阻断级（P0）问题确认：
  - `api/tasks.py` 状态迁移采用“先读后写”，缺少 CAS 与幂等键，存在重复入队与多 job 覆盖。
  - `api/tasks.py` 在部分路径先提交状态再入队，存在“状态已推进但 job 未创建”的空窗。
  - `workers/video_tasks.py` 缺少执行令牌/版本约束，陈旧 worker 可覆盖终态。
  - `services/video_processor.py` fallback 分支 `Popen(...PIPE...) + wait()` 未消费管道，存在真实阻塞并误判超时。
  - `services/video_processor.py` 多个超时分支 `kill()` 后未 `wait()`，存在僵尸进程/句柄泄漏风险。
  - SSE 错误事件与前端消费协议不一致，可能将无效 payload 写入 UI 状态。
- 高优先（P1）问题确认：
  - `_get_queue` 重试是线性退避且无 jitter，Redis 故障时会形成重试同频波峰。
  - worker 捕获异常后返回失败对象不抛出，队列层重试失效。
  - 前端 `REVIEW_APPROVED` 状态闭环不完整，可能出现“活跃但不可观测”状态空洞。
  - 前端进度采用 `Math.max(local, polling)`，断线/阶段切换时可能卡在高进度假象。

## 2026-03-01 并发专项修复落地结果
- 后端任务编排（`api/tasks.py`）：
  - 新增 `active_operation/active_job_id` 状态字段并接入响应载荷。
  - `process/review/approve` 改为“先 enqueue（支持 Idempotency-Key）再 CAS 认领状态”。
  - 入队去重与失败补偿：CAS 失败时对新建 job 做 best-effort cancel，并返回幂等结果或 409。
  - `return-to-review` 改为 CAS 迁移，避免并发下非法回退。
- worker 防陈旧覆盖（`workers/video_tasks.py`）：
  - 所有状态/进度更新改为 `active_job_id` 约束写入。
  - 增加短暂认领等待窗口，消除“先入队后 CAS”极短竞态导致的误 stale。
  - 成功终态会清空 `active_operation/active_job_id`；失败分支支持“有剩余重试则不提前写 FAILED”。
- 子进程稳定性（`services/video_processor.py`）：
  - 新增统一子进程回收函数（kill + wait + close pipes）。
  - fallback 重编码从 `Popen+wait` 改为 `subprocess.run + DEVNULL`，移除 pipe 堵塞风险。
- SSE 协议与前端消费（`api/progress.py` + `taskService/useTaskProgress`）：
  - SSE 事件统一为 `type=progress|terminal|error`，补齐 `error_code/error_message/timestamp`。
  - 前端新增 payload 解析与 schema 守卫，错误事件不再污染 status/progress。
  - 前端连接范围纳入 `REVIEW_APPROVED`，并按 timestamp 丢弃旧事件，避免状态回退。
- 前端重试与展示（`main.tsx`、`TaskListItem.tsx`、`TaskCard.tsx`）：
  - React Query 重试改为按状态码分级 + `Retry-After` + jitter。
  - 进度展示去除“只增不减”策略，允许回落到真实进度。

## 2026-03-01 实现后审阅修正（第二轮）
- 将任务入口编排调整为 `CAS 认领 -> enqueue -> enqueue 失败回滚`，避免 worker 启动早于认领造成 stale 退出。
- `return-to-review` 调整为“先清理文件，再事务内更新状态+删除 Scene”，规避部分提交。
- `_build_retry_policy` 支持 `RQ_JOB_RETRY_MAX=0`（不注入 `retry` 参数）。
- `_enqueue_with_dedup` 只复用活跃 job；命中终态 job + 同 key 直接返回 409，避免死 job 复用。

## 2026-03-01 Phase-3 稳态增强落地
- 限流能力升级（`core/rate_limit.py`）：
  - 新增 `RATE_LIMIT_BACKEND=redis|memory`，支持 Redis 共享滑动窗口；
  - Redis 不可用时自动降级内存桶，保障可用性；
  - 限流维度改为 `bucket + (token 或 ip) + route`；
  - 新增 `RATE_LIMIT_TRUST_PROXY_HEADERS` 控制是否信任 `x-forwarded-for`。
- 观测能力增强（`core/telemetry.py` + 调用侧接入）：
  - 新增计数器 `duplicate_enqueue_detected_total`、`stale_worker_write_blocked_total`、`ffmpeg_timeout_total`；
  - 新增结构化日志 `event_type/task_id/job_id/retry_attempt` 等字段；
  - 新增 `GET /api/metrics/counters` 输出进程级计数快照。
- 前端 SSE 健壮性观测：
  - 新增客户端计数 `sse_invalid_payload_total`（`frontend/src/utils/telemetry.ts`），并在 SSE 解析失败/非法 payload 时递增。
