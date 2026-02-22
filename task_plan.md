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
