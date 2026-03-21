# Workflow

## 目标

这份文档用于固定 `scene-workbench` 的日常开发、真实视频验证和交付节奏。

核心原则：

- `examples/` 放稳定样例
- `evaluation/runs/` 放本地运行产物
- `manifest.transnet.json` 保留算法原始输出
- `manifest.review.json` 承接人工 review 动作

## 目录约定

- `src/scene_workbench/`
  项目实现
- `tests/`
  回归测试
- `examples/`
  只读样例与接口契约
- `evaluation/`
  示例 baseline 与评估说明
- `evaluation/runs/`
  本地真实视频验证产物（默认不纳入 Git 基线）
- `scripts/`
  环境恢复与辅助脚本

## 环境准备

首次或环境损坏时，优先使用脚本恢复：

```powershell
.\scripts\rebuild-venv.ps1
```

预演模式：

```powershell
.\scripts\rebuild-venv.ps1 -WhatIf
```

如果只想手动安装：

```powershell
python -m pip install ".[dev,web,refine]"
```

## 日常开发回路

推荐顺序：

1. 改代码
2. 跑相关测试
3. 跑全量测试
4. 同步 README / evaluation 文档

最常用命令：

```powershell
python -m pytest -q
python -m scene_workbench --version
```

## 真实视频验证流程

### 1. 生成算法原始输出

```powershell
python -m scene_workbench analyze <video> --output evaluation\runs\<slug>\<date>\manifest.transnet.json
```

### 2. 收集结构化评估结果

```powershell
python -m scene_workbench inspect evaluation\runs\<slug>\<date>\manifest.transnet.json
python -m scene_workbench baseline evaluation\runs\<slug>\<date>\manifest.transnet.json --output-json evaluation\runs\<slug>\<date>\baseline.json --output-md evaluation\runs\<slug>\<date>\baseline.md
```

### 3. 切到人工 review 工作集

复制一份 review 专用 manifest，避免人工动作污染算法原始输出：

```text
manifest.transnet.json  ->  manifest.review.json
```

### 4. 启动 review harness

```powershell
python -m scene_workbench review evaluation\runs\<slug>\<date>\manifest.review.json --no-open-browser
```

review harness 当前支持：

- `accept`
- `reject`
- `adjust`
- `merge`
- `insert`

并且：

- 动作后自动保存
- 优先跳到下一个 `unreviewed` boundary
- 非法命令返回 `400/422`，不应返回 `500`

### 5. 导出 reviewed-only 结果

```powershell
python -m scene_workbench export evaluation\runs\<slug>\<date>\manifest.review.json --format json --output evaluation\runs\<slug>\<date>\export.reviewed.json
```

## 样例文件维护规则

`examples/manifest.v1.example.json` 是测试与文档共用的稳定样例。

维护要求：

- 不用它承接真实 review 动作
- 不在调试时直接覆盖它
- 变更它时，必须同步：
  - `tests/`
  - `evaluation/baseline.example.json`
  - `evaluation/baseline.example.md`

建议同步命令：

```powershell
python -m scene_workbench baseline examples\manifest.v1.example.json --output-json evaluation\baseline.example.json --output-md evaluation\baseline.example.md
```

## Git 基线规则

`clsp` 应作为独立项目维护 Git 基线。

基线目标：

- 只提交源码、测试、样例、文档、脚本
- 不提交 `.venv/`、`.pytest_cache/`、`.codex-plans/`
- 不提交 `evaluation/runs/` 下的本地运行产物
- 不提交 `__pycache__/` 和 `*.pyc`

如果某次真实验证结果值得长期保留：

- 优先沉淀为：
  - 文档结论
  - 稳定样例
  - 回归测试
  - 自动化脚本

而不是直接提交整包运行产物。

## Definition of Done

一轮改动至少满足：

- 相关测试通过
- 全量测试通过
- README / evaluation 文档已同步
- 样例 fixture 未被污染
- 真实验证产物留在 `evaluation/runs/`
