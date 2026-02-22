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
