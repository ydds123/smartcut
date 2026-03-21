# 10 Agent 并行分工方案

## 总体原则

- 单轮最多并行 5 个任务
- 只并行无写冲突任务
- 强依赖链必须串行
- 每个 Agent 必须有明确 ownership
- 主控负责整合、冲突检查和回归验证

## 推荐 Agent 角色

### core_models_worker

- 任务定义：落地 manifest、config、review action 相关模型与契约
- 执行动作：实现 `models.py`、`config.py`
- 写入范围：
  - `src/scene_workbench/models.py`
  - `src/scene_workbench/config.py`
- 预期结果：核心数据模型与 schema 对齐

### ingest_detector_worker

- 任务定义：落地视频元信息读取与 PySceneDetect 粗切
- 执行动作：实现 `ingest/media.py`、`detectors/pyscenedetect_runner.py`
- 写入范围：
  - `src/scene_workbench/ingest/`
  - `src/scene_workbench/detectors/pyscenedetect_runner.py`
- 预期结果：输入本地视频可得到 `VideoSource` 与 `coarse_boundaries`

### refinement_worker

- 任务定义：落地 suspicious windows 与 TransNetV2 refinement
- 执行动作：实现 `suspicious_windows.py`、`transnetv2_runner.py`
- 写入范围：
  - `src/scene_workbench/detectors/suspicious_windows.py`
  - `src/scene_workbench/detectors/transnetv2_runner.py`
- 预期结果：给定 coarse 结果可生成 `SuspiciousWindow[]` 和 refined candidates

### fusion_worker

- 任务定义：落地 coarse / refined 融合与 final boundary 裁决
- 执行动作：实现 `fusion/decision.py`
- 写入范围：
  - `src/scene_workbench/fusion/`
- 预期结果：能输出稳定 `final_boundaries`

### review_worker

- 任务定义：落地 manifest 读写、apply_review_action 与最小 web review
- 执行动作：实现 `review/` 与 `web/`
- 写入范围：
  - `src/scene_workbench/review/`
  - `src/scene_workbench/web/`
- 预期结果：review harness 可浏览、修改并保存 manifest

### cli_export_worker

- 任务定义：落地 CLI 和导出能力
- 执行动作：实现 `cli.py` 与 `export/`
- 写入范围：
  - `src/scene_workbench/cli.py`
  - `src/scene_workbench/export/`
- 预期结果：analyze / review / export 命令和导出格式可用

### eval_worker

- 任务定义：建立最小评估集并跑第一轮评估
- 执行动作：收集样本、定义基线、记录结果
- 写入范围：
  - 评估样本目录
  - 评估结果文档
- 预期结果：第一轮 baseline 评估数据形成

## Wave 1

并行任务：

- `core_models_worker`
- `ingest_detector_worker`

理由：

- 写入范围不冲突
- 后续 refinement、fusion、review 都依赖这两块

集成检查点：

- 核心模型已稳定
- 本地视频可读取元信息
- PySceneDetect 可跑出 coarse 结果

## Wave 2

并行任务：

- `refinement_worker`
- `fusion_worker`

依赖：

- Wave 1 完成

理由：

- refinement 依赖 coarse
- fusion 依赖 manifest 结构与 detector 输出约定

集成检查点：

- suspicious windows 生成
- refined candidates 可输出
- final boundaries 可生成

## Wave 3

并行任务：

- `review_worker`
- `cli_export_worker`

依赖：

- Wave 2 完成

理由：

- review 依赖 final boundary 语义稳定
- export 依赖 `final_boundaries` 结构稳定

集成检查点：

- 本地 Web review 可打开
- `apply_review_action()` 可落地
- CLI analyze/review/export 主链打通

## Wave 4

并行任务：

- `eval_worker`
- 主控整合与回归验证

依赖：

- Wave 3 完成

理由：

- 此时系统已具备完整闭环
- 可以开始评估碎切、漏切与人工确认成本

集成检查点：

- 有第一轮 baseline
- 有回归验证结果
- 可支持下一轮参数调整

## 串行依赖说明

- `fusion` 必须在 detector 输出结构稳定后推进
- `review` 必须在 manifest 与 `apply_review_action` 语义稳定后推进
- `export` 必须在 `final_boundaries` 语义稳定后推进
- `evaluation` 必须在 review 流程可用后推进

## 主控职责

主控不直接承担大块实现，而负责：

- 波次调度
- 依赖管理
- 冲突检查
- 集成验证
- 基线结果汇总

## 推荐使用方式

如果按多 Agent 并行推进，推荐顺序：

1. 先按 `09-issue-cards.md` 建 issue
2. 再按本文件分配 ownership
3. 每一轮完成后做一次集成检查
