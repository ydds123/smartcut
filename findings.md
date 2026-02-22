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
