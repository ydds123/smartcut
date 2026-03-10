# Progress Log - SmartCut

## 2026-02-19
- 复现并确认：前端 5173 在，后端 8000 不稳定时会直接触发 `Network Error`。
- 修复配置：前端/代理/环境变量统一到 `127.0.0.1:8000`，后端启动脚本固定 `.venv` 解释器。
- 补齐兼容：CORS 增加 `http://127.0.0.1:5173`。
- 无头 E2E 回归通过（指定视频）：任务最终 `COMPLETED/100/57 scenes`。

## 当前建议
- 修改配置后必须重启前端 dev server（Vite 会缓存旧 `.env` 与代理配置）。
- 后端使用 `backend/run.sh` 或等效 `.venv` 命令启动。

## 2026-02-19（稳定性改造补充）
- 已实现跨平台服务守护工具 `tools/devstack.py`（支持 Win/Mac）。
- 已增加一键命令：`up/down/status/ps/restart/logs/doctor`。
- `restart` 支持单服务重启：`python tools/devstack.py restart backend`。
- 已更新 `README.md` 与 `测试指南.md` 的启动流程为 devstack 优先。

## 2026-02-20（TransNet 精确模式修复）
- 重构 `app/services/transnet_architecture.py`，对齐官方 TransNetV2 PyTorch 推理结构。
- 重构 `app/services/transnet_detector.py`：
  - 输入改为 27x48 RGB uint8
  - 统一窗口推理与峰值提取
  - 增加权重完整性校验与清晰错误日志
- 更新 `app/services/download_transnet_model.py` 失败提示，改为官方转换流程指引。
- 已重启 `backend + worker` 并完成无头精确模式回归。
- 结果：维度报错消失；当前受本地无效权重限制，精确模式走稳定回退。

## 2026-02-20（权重来源补充）
- 官方仓库 `git lfs pull` 因上游 LFS 配额超限失败，无法通过官方仓库直接下载 TF 权重文件。
- 已安装 `git-lfs` 并完成本地验证，确认阻塞来自远端预算。
- 采用临时替代权重源（PyPI 包内权重）并替换 `~/.smartcut/models/transnetv2-pytorch-weights.pth`。
- 已将 `transnet_detector` 的最小 key 校验阈值从 120 调整为 80（官方兼容权重为 90 keys）。
- 回归结果：precision 模式不再回退，TransNet 融合生效。

## 2026-02-20（镜头合理性问题修复）
- 新增 `TransNetV2Detector.score_candidates`，支持对候选边界做软评分。
- 调整融合逻辑：引入 `soft_candidate_threshold`，提升顺滑过渡候选保留能力。
- 新增边界级最小间隔约束和场景级最小时长合并（默认 >= 1 秒）。
- 无头回归验证通过：最终镜头最短时长 > 1 秒，且融合模式仍为 `pyscene+transnet`。

## 2026-02-23（代码审阅优化）
- 已读取并核对 `code_review.md` 涉及文件：`file_service.py`、`video_processor.py`、`video_tasks.py`、`api/tasks.py`、`useTasks.ts`、`App.tsx`、`uiStore.ts`。
- 已完成修复方案分解：后端优先（超时、容错、输入校验、队列初始化）→ 前端（轮询、Error Boundary、Toast ID）→ 回归验证。
- 当前处于实施前准备完成状态，下一步开始逐文件改动。

## 2026-02-23（代码审阅优化实施结果）
- 后端：
  - `upload` 链路接入 magic bytes 文件头校验（异步读取并恢复文件指针）。
  - `tasks` 路由改为 RQ 懒加载 + Redis 重试连接，避免导入时崩溃。
  - `save_review_data` 改为 Pydantic schema 入参，并增加有序/重叠约束。
  - `video_processor` 增加 FFmpeg/ffprobe 超时与 kill 处理。
  - `video_processor` + `video_tasks` 改为“部分场景成功即可完成任务”，并记录失败统计指标。
  - `models` 默认时间函数替换 `datetime.utcnow`。
- 前端：
  - `useTasks` 改为活跃任务智能轮询。
  - 新增全局 `AppErrorBoundary` 并在 `main.tsx` 接入。
  - Toast ID 改为 `crypto.randomUUID()` 优先策略。
- 新增/更新测试：
  - 新增 `test_file_type_validation.py`（上传魔数校验）。
  - 新增 `test_review_data_schema.py`（审核场景 schema）。
  - 扩展 `test_incremental_split.py`（部分成功聚合逻辑）。

## 2026-02-23（回归验证）
- `python3 -m unittest test_incremental_split.py test_file_type_validation.py test_review_data_schema.py` 通过（9 tests）。
- `python3 -m compileall app` 通过。
- `npx tsc --noEmit` 通过。

## 2026-02-23（后续加固）
- 新增 `app/core/security.py`：可开关 API token 认证依赖（Header + Query 双通道）。
- 新增 `app/core/rate_limit.py`：轻量内存限流器（429 + Retry-After）。
- `main.py` 接入 `/api` 全局认证依赖，并为 `/data` 增加“公开挂载/受保护路由”切换。
- `upload.py` 和 `tasks.py` 的写接口接入限流。
- `taskService.ts` / `api.ts` 接入 `VITE_API_TOKEN`（API Header + SSE Query）。
- 新增测试 `test_data_path_access.py`，覆盖受保护数据路径 token 拼接逻辑。
- 更新 `README.md` 环境变量说明与启用示例。

## 2026-02-23（后续加固回归）
- `python3 -m unittest test_incremental_split.py test_file_type_validation.py test_review_data_schema.py test_data_path_access.py` 通过（11 tests）。
- `python3 -m compileall app` 通过。
- `npx tsc --noEmit` 通过。

## 2026-02-23（参数配置元数据统一）
- 新增 `app/services/processing_param_specs.py`，集中维护所有处理参数元数据（默认值、范围、推荐区间、来源标记）。
- `quality_tuning.py` 改为完全依赖参数规范模块生成 `DEFAULT_QUALITY_CONFIG` 与 `_normalize_quality_config`。
- `tasks.py` 新增 `GET /api/config/processing-meta`，并在 `process/review` 响应中返回 `config_meta`。
- 前端完成动态化改造：
  - `taskService` 增加 `getProcessingConfigMeta` 与响应归一化；
  - `processingConfigSettings` 支持基于后端 defaults 构建本地默认设置；
  - `ProcessingConfigModal` 改为按后端 fields/groups 渲染，不再硬编码数值边界。
- 兼容性修复：
  - `downscale=0` 明确作为 auto 语义；
  - `frame_skip>0` 时禁用 stats 输出，避免 PySceneDetect 参数组合报错。
- 新增测试 `test_processing_param_specs.py` 覆盖规范一致性与响应结构。

## 2026-03-01（并发稳定性专项审查启动）
- 已按关键词完成首轮热区扫描：`timeout/retry/status/progress/queue/commit`。
- 计划并行派发 4 个 `explorer` 子智能体：
  - 并发与竞态（worker + api 状态迁移）
  - 超时与子进程回收（video_processor + ffprobe/ffmpeg）
  - 重试策略与退避（Redis/RQ + 质量调优重试）
  - 前后端状态同步（SSE + 轮询 + UI 状态合并）

## 2026-03-01（并发稳定性专项审查完成）
- 已完成 4 个 `explorer` 并行审查并收敛结果。
- 已识别并去重以下阻断级问题：
  - 状态迁移非原子 + 入队幂等缺失（重复 job）。
  - 状态提交与入队分离导致中间态泄露。
  - worker 缺少执行代际保护（陈旧写覆盖终态）。
  - FFmpeg fallback 管道阻塞与 kill 后未回收。
  - SSE 错误 payload 协议不一致与前端状态机断档。
- 已形成按严重度排序的修复建议，待执行阶段可按 “CAS+幂等键 → worker 令牌化 → 子进程回收统一化 → SSE 协议校验与状态机闭环” 推进。

## 2026-03-01（并发稳定性专项修复实施）
- 后端：
  - `Task` 模型新增 `active_operation`、`active_job_id`，并在 DB 兼容升级逻辑中补齐列。
  - `api/tasks.py` 实现入队去重与 CAS 状态迁移；`process/review/approve` 返回 `deduplicated` 标记。
  - `_get_queue` 退避改为指数退避 + jitter。
  - `workers/video_tasks.py` 全链路写库接入 `active_job_id` 保护，防止陈旧 job 覆盖终态。
  - worker 异常路径支持“有 retries_left 时先抛异常重试，不提前写 FAILED”。
  - `video_processor.py` 修复 fallback 管道阻塞与 kill 后未回收问题。
  - `progress.py` SSE 事件统一为 `progress/terminal/error` 协议。
- 前端：
  - `taskService` 新增 SSE payload 解析与校验，mutation 请求默认带 `Idempotency-Key`。
  - `useTaskProgress` 接入错误事件处理、连接状态修复、`REVIEW_APPROVED` 实时跟踪、时间戳去旧。
  - `TaskListItem`/`TaskCard` 去除 `Math.max(local, polling)` 的只增不减合并。
  - `main.tsx` 将 Query retry 改为状态码分级 + `Retry-After` + jitter。
- 新增测试：
  - `test_task_queue_idempotency.py`（任务 job_id 生成/幂等 key 规范化 + SSE 事件 schema）。
- 回归结果：
  - `python3 -m unittest test_incremental_split.py test_review_data_schema.py test_file_type_validation.py test_processing_param_specs.py test_task_queue_idempotency.py` 通过（21 tests）。
  - `python3 -m compileall app` 通过。
  - `npx tsc --noEmit` 通过。

## 2026-03-01（实现后代码审阅回合）
- 已按 `requesting-code-review` 执行实现后审阅，并修复返回问题：
  - `enqueue -> CAS` 改为 `CAS -> enqueue` 且失败补偿回滚，消除 worker 提前 stale 导致卡死。
  - `return-to-review` 调整为“先文件清理、后单事务状态+Scene 更新”，避免部分提交不一致。
  - `RQ_JOB_RETRY_MAX=0` 场景兼容：不再构造 `Retry(max=0)`。
- 终态 job 不再参与幂等复用，重复 Idempotency-Key 将返回 409，避免绑定死 job。
- 审阅后再次执行同一组验证，结果均通过。

## 2026-03-01（Phase-3 稳态增强实现）
- 新增 `backend/app/core/telemetry.py`，提供轻量计数器与结构化日志工具。
- 限流从“仅进程内”升级为“Redis 共享桶 + 内存自动降级”，并支持代理头信任开关。
- `api/tasks.py` 接入结构化事件日志与重复入队计数。
- `workers/video_tasks.py` 接入 stale 写阻断计数与 worker 重试结构化日志。
- `services/video_processor.py` 在 FFmpeg 超时路径接入计数与结构化日志。
- `api/tasks.py` 新增 `GET /api/metrics/counters` 指标快照接口。
- 前端新增 `src/utils/telemetry.ts`，在 SSE 非法 payload/解析失败时累计 `sse_invalid_payload_total`。
- 新增测试 `backend/test_rate_limit_identity.py`，并扩展 `test_task_queue_idempotency.py` 覆盖 Retry=0 与终态 job idempotency 冲突场景。

## 2026-03-01（Phase-3 回归验证）
- `python3 -m unittest test_incremental_split.py test_review_data_schema.py test_file_type_validation.py test_processing_param_specs.py test_task_queue_idempotency.py test_rate_limit_identity.py` 通过（26 tests）。
- `python3 -m compileall app` 通过。
- `npx tsc --noEmit` 通过。
