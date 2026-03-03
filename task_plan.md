# Task Plan - SmartCut Network Error 排障

## 目标
修复前端 `Network Error`，确保 `http://127.0.0.1:8000/api/tasks` 稳定可用，并完成一次无头端到端验证。

## 阶段
- [completed] 阶段1: 环境与服务存活性检查（5173/8000、日志、API）
- [completed] 阶段2: 服务栈稳定化（后端启动方式、IPv4/IPv6 地址统一）
- [completed] 阶段3: 无头E2E回归（上传指定视频、触发处理、进度到100）
- [completed] 阶段4: 总结根因与操作建议

## 错误记录
| 时间 | 错误 | 尝试 | 结论 |
|---|---|---|---|
| 2026-02-19 | 前端 `net::ERR_CONNECTION_REFUSED` | 检查 8000 监听与 curl | 后端未稳定监听是直接原因 |
| 2026-02-19 | 无头脚本失败（引号解析） | 改为临时 Python 脚本执行 | 修复脚本后稳定运行 |
| 2026-02-19 | `/api/upload` 返回 400 Invalid file type | curl 增加 `;type=video/mp4` | 非浏览器上传需显式 MIME |

## 关键结论
1. `localhost:8000` 在部分环境会解析到 `::1`，而后端常在 IPv4 监听，导致连接拒绝。
2. 统一使用 `127.0.0.1:8000` 可规避该类网络错误。
3. 前端环境变量/代理/缩略图地址需统一到同一后端基址。

## 后续增强（2026-02-19）
- [completed] 新增跨平台 `devstack` 守护启动器（Windows + macOS）
- [completed] 支持一键 `up/down/status/ps/restart/logs/doctor`
- [completed] `restart` 支持单服务重启（`restart backend|worker|frontend`）
- [completed] 支持自动重启与限频熔断，降低服务掉线导致的“加载失败”

## 后续增强（2026-02-20）
- [completed] 阶段5: 替换 TransNet 推理为官方兼容架构（输入 `27x48 RGB uint8`）
- [completed] 阶段6: 增加权重有效性校验（最小文件大小 + 关键权重键 + 覆盖率）
- [completed] 阶段7: 精确模式烟测与回退验证（无有效权重时稳定回退）

## 新增错误记录
| 时间 | 错误 | 尝试 | 结论 |
|---|---|---|---|
| 2026-02-20 | `mat1 and mat2 shapes cannot be multiplied` | 对齐官方 TransNetV2 架构并修正输入窗口管线 | 维度错误已消失 |
| 2026-02-20 | 精确模式仍无融合结果 | 校验模型文件完整性 | 根因是本地权重仅 122071 bytes（无效），已改为明确拒绝并回退 |

## 权重获取阶段（2026-02-20）
- [completed] 阶段8: 按官方流程执行权重拉取（clone + git-lfs）并定位阻塞
- [completed] 阶段9: 采用替代权重来源恢复 precision 融合可用性

## 补充错误记录
| 时间 | 错误 | 尝试 | 结论 |
|---|---|---|---|
| 2026-02-20 | `git lfs pull` 报仓库 LFS budget exceeded | 安装 `git-lfs` 后重试 | 上游仓库配额问题，非本地问题 |
| 2026-02-20 | 新权重被拒绝（key 数阈值过高） | 对比模型 `state_dict` 实际键数 | 将阈值调为 80 后通过加载 |

## 镜头合理性修复（2026-02-20）
- [completed] 阶段10: 增加最小镜头时长硬约束（默认 >=1 秒）
- [completed] 阶段11: 增加软过渡候选评分通道并接入融合
- [completed] 阶段12: 精确模式回归验证（最短镜头检查 + 融合状态检查）

## 代码审阅优化（2026-02-23）
## 目标
根据 `code_review.md` 落地高价值修复，优先解决稳定性与输入校验问题，确保改动有回归验证。

## 阶段
- [completed] 阶段1: 基于审阅报告定位代码并确认可实施范围
- [completed] 阶段2: 后端修复（超时、部分失败策略、上传魔数校验、队列懒加载、schema 校验）
- [completed] 阶段3: 前端修复（智能轮询、全局错误边界、Toast ID）
- [completed] 阶段4: 回归验证与结果归档

## 本轮约束
1. 不做破坏现有本地开发流的强制认证改造（认证与静态目录访问控制先不引入 breaking change）。
2. 对外行为改动以“容错增强”为主，避免改变正常流程返回结构。

## 验证结果
1. 后端单测：`python3 -m unittest test_incremental_split.py test_file_type_validation.py test_review_data_schema.py`（9/9 通过）。
2. 后端语法编译：`python3 -m compileall app`（通过）。
3. 前端类型检查：`npx tsc --noEmit`（通过）。

## 后续加固（2026-02-23）
- [completed] 阶段5: 可开关 API Token 认证（后端依赖 + 前端请求头/SSE 适配）
- [completed] 阶段6: 轻量速率限制（上传/写操作接口）
- [completed] 阶段7: `/data` 访问控制开关（公开挂载 vs 受保护文件路由）
- [completed] 阶段8: 文档与回归验证补充

## 后续加固验证结果
1. 后端单测：`python3 -m unittest test_incremental_split.py test_file_type_validation.py test_review_data_schema.py test_data_path_access.py`（11/11 通过）。
2. 后端语法编译：`python3 -m compileall app`（通过）。
3. 前端类型检查：`npx tsc --noEmit`（通过）。

## 参数配置统一（2026-02-23）
## 目标
将参数配置的 `default/min/max/step/recommendedRange` 抽离为后端单一事实源，并确保 `pyscenedetect` 参数边界对齐官方约束。

## 阶段
- [completed] 阶段1: 建立后端参数规范模块（含 provenance/source_ref）
- [completed] 阶段2: 重构 `quality_tuning` 归一化与默认值来源
- [completed] 阶段3: API 暴露 `config_meta`（process/review/meta endpoint）
- [completed] 阶段4: 前端参数面板改为消费后端元数据
- [completed] 阶段5: 回归验证（backend unittest + compileall + frontend lint/build）

## 本轮验证
1. `python3 -m unittest test_processing_param_specs.py test_pyscenedetect_resilience.py`（6/6 通过）。
2. `python3 -m compileall app`（通过）。
3. `npm run lint`（通过）。
4. `npm run build`（通过）。

## 并发稳定性专项审查（2026-03-01）
## 目标
并行审查并定位并发、超时、重试、状态同步相关的致命风险，输出阻断级问题清单与修复优先级。

## 阶段
- [completed] 阶段1: 热点扫描与模块分派（backend worker/api/progress + frontend SSE/poll）
- [completed] 阶段2: 多智能体并行深审（并发/超时/重试/状态同步四条线）
- [completed] 阶段3: 风险去重与严重度排序
- [completed] 阶段4: 形成审查结论与修复建议

## 并发稳定性专项修复（2026-03-01）
## 目标
按优先级落地阻断级修复（幂等入队、状态原子迁移、worker 代际防护、FFmpeg 子进程治理、SSE 协议一致性），并完成回归验证。

## 阶段
- [completed] 阶段1: 后端任务状态机止血（enqueue+CAS、active_job 守护、approve/return 原子化）
- [completed] 阶段2: worker 防陈旧覆盖（active_job 校验、终态清理、重试前不提前 failed）
- [completed] 阶段3: FFmpeg fallback 管道阻塞与 kill 后回收修复
- [completed] 阶段4: SSE 协议标准化与前端消费校验（error/progress/terminal）
- [completed] 阶段5: 前端状态闭环修复（REVIEW_APPROVED、进度合并策略、重试策略分级）
- [completed] 阶段6: 回归验证（backend unittest + compileall + frontend tsc）

## 本轮验证
1. `python3 -m unittest test_incremental_split.py test_review_data_schema.py test_file_type_validation.py test_processing_param_specs.py test_task_queue_idempotency.py`（21/21 通过）。
2. `python3 -m compileall app`（通过）。
3. `npx tsc --noEmit`（通过）。

## Phase-3 稳态增强（2026-03-01）
## 目标
落地共享限流与观测增强，补齐告警前置指标并完成回归。

## 阶段
- [completed] 阶段1: Redis 共享限流 + 内存降级兜底
- [completed] 阶段2: 结构化日志字段接入（task_id/job_id/event_type/retry_attempt）
- [completed] 阶段3: 关键计数器接入（duplicate/stale/ffmpeg_timeout/sse_invalid_payload）
- [completed] 阶段4: 指标快照接口与测试补齐
- [completed] 阶段5: 回归验证（backend unittest + compileall + frontend tsc）

## 本轮验证
1. `python3 -m unittest test_incremental_split.py test_review_data_schema.py test_file_type_validation.py test_processing_param_specs.py test_task_queue_idempotency.py test_rate_limit_identity.py`（26/26 通过）。
2. `python3 -m compileall app`（通过）。
3. `npx tsc --noEmit`（通过）。
