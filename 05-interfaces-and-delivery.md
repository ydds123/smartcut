# 05 接口与交付

## 目标

定义 V1 的 Python API、CLI、导出格式与模块边界，让算法、前端、CLI 和下游集成可以并行开发。

## Python API

建议暴露高层接口：

- `analyze_video(video_path, config=None) -> ProjectManifest`
- `detect_coarse(video_path, config=None)`
- `refine_windows(video_path, windows, config=None)`
- `fuse_boundaries(coarse, refined, config=None)`
- `apply_review_action(manifest, action)`
- `export_json(manifest, output_path)`
- `export_edl(manifest, output_path)`
- `export_ffmpeg_split(manifest, output_path)`
- `export_cut_list(manifest, output_path)`

原则：

- API 以 `ProjectManifest` 为统一输入输出中心
- 检测层、审阅层、导出层职责分离

## CLI

建议统一使用：

```text
scene-workbench <command>
```

V1 推荐命令：

- `analyze`
- `review`
- `export`
- `inspect`

示例：

```bash
scene-workbench analyze input.mp4 --output manifest.json
scene-workbench review manifest.json
scene-workbench export manifest.json --format edl --output result.edl
scene-workbench inspect manifest.json
```

## 导出格式

V1 先支持：

- JSON
- 时间戳列表
- EDL
- FFmpeg 切分命令

规则：

- 所有导出都基于 `final_boundaries`
- 默认只导出人工确认后的活动工作集

## 模块边界

推荐模块拆分：

- `ingest/`：视频元信息读取
- `detectors/`：粗切、精切、suspicious windows
- `fusion/`：多源结果融合与裁决
- `review/`：人工动作、状态存储、预览辅助
- `export/`：标准导出
- `web/`：最小 review harness

## 项目文件结构建议

建议第一版代码结构按下列方式组织：

```text
scene_workbench/
├─ pyproject.toml
├─ README.md
├─ src/
│  └─ scene_workbench/
│     ├─ api.py
│     ├─ cli.py
│     ├─ models.py
│     ├─ config.py
│     ├─ ingest/
│     ├─ detectors/
│     ├─ fusion/
│     ├─ review/
│     ├─ export/
│     └─ web/
├─ tests/
└─ examples/
```

## 模块职责定义

- `models.py`：核心数据结构
- `config.py`：配置解析与默认值
- `ingest/`：视频元信息读取
- `detectors/`：粗切、精切、可疑窗口生成
- `fusion/`：边界融合与规则裁决
- `review/`：人工修正动作与 manifest 状态更新
- `export/`：导出 JSON / EDL / FFmpeg / cut list
- `web/`：最小 review harness

## 实现顺序建议

建议按三阶段推进：

### M1：先打通数据流

- models
- ingest
- coarse detection
- suspicious windows
- refinement
- fusion
- analyze CLI

### M2：打通人工确认层

- review actions
- store
- preview 辅助
- 最小 web review

### M3：打通交付层

- JSON 导出
- cut list
- EDL
- FFmpeg split

## 哪些先 stub，哪些必须一次做对

可以先 stub：

- `transnetv2_runner.py`
- `edl_exporter.py`
- `web/app.py` 的复杂交互

必须一次做对：

- manifest 结构
- `BoundaryCandidate`
- `final_boundaries` / `review_actions` 分层
- 以 `frame` 为主的时基设计

## 建议的最小技术选型

建议最小技术栈：

- `pydantic`
- `typer`
- `PySceneDetect`
- `TransNetV2`
- `opencv-python` 或 `ffmpeg-python`
- `FastAPI` 或 `Flask`
- `jinja2`

## 文件结构建议

建议采用 Python core + CLI + 本地 Web review 的轻量结构。

理由：

- 易脚本化
- 易嵌入
- 易后续扩展成 SDK

## 交付原则

V1 交付的重点不是“支持最多集成”，而是：

- 同一份 manifest 能贯穿检测、审阅、导出
- 接口稳定
- 模块职责清晰
- 可以支持后续替换 detector 而不重写 review 或 export

## 第一版 CLI 命令完整建议

```bash
scene-workbench analyze input.mp4 --output manifest.json
scene-workbench analyze input.mp4 --coarse-only --output manifest.json
scene-workbench review manifest.json
scene-workbench export manifest.json --format json --output out.json
scene-workbench export manifest.json --format cutlist --output cuts.txt
scene-workbench export manifest.json --format edl --output result.edl
scene-workbench export manifest.json --format ffmpeg --output split.sh
scene-workbench inspect manifest.json
```

## apply_review_action() 的说明与调用位置

`apply_review_action()` 建议作为 review 层的核心状态变更入口。

它的调用位置包括：

- 本地 Web review harness
- CLI 交互式修订命令
- 未来可能的 SDK / API 层

详细行为规范与伪代码不直接塞进主文档，统一放在：

- [`review-actions.example.md`](E:/上虞园区数据对接/处理视频资料/examples/review-actions.example.md)
