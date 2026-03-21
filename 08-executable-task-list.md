# 08 可执行开发任务清单

## 相关文档导航

- `08`：里程碑级任务总览
- [`09-issue-cards.md`](E:/上虞园区数据对接/处理视频资料/09-issue-cards.md)：可直接排期、建 issue 的任务卡
- [`10-agent-parallel-plan.md`](E:/上虞园区数据对接/处理视频资料/10-agent-parallel-plan.md)：可并行执行的 Agent 分工与调度方案

## 目标

将当前 V1 方案拆解为可直接执行的开发任务，支持按里程碑推进，并尽量减少模块间依赖冲突。

本清单覆盖：

- M1：检测链路与 manifest 落盘
- M2：review harness 与人工修正
- M3：导出、评估与收尾

## 总体推进顺序

```text
M1 检测链路
→ M2 review harness
→ M3 导出与评估
```

建议原则：

- 先打通数据流，再做界面
- 先支持本地文件，再考虑 URL / 下载
- 先交付“可确认结果”，再优化检测质量

---

## M1：检测链路与 Manifest

### T1. 建项目骨架

目标：

- 创建 Python 项目目录结构
- 建好 `src/scene_workbench/` 与 `tests/`
- 放置 CLI 入口、基础依赖配置

交付物：

- `pyproject.toml`
- `src/scene_workbench/`
- `tests/`

验收标准：

- 本地可安装依赖
- 能执行空的 CLI 命令入口

依赖：

- 无

### T2. 落地核心数据模型

目标：

- 将 manifest 相关数据结构正式实现到代码中

交付物：

- `models.py`
- `config.py`

必须实现：

- `VideoSource`
- `BoundaryCandidate`
- `SuspiciousWindow`
- `ReviewAction`
- `ReviewActionCommand`
- `ProjectManifest`

验收标准：

- 能从样例 JSON 成功反序列化
- 与 `manifest.v1.schema.json` 字段命名一致

依赖：

- T1

### T3. 实现视频元信息读取

目标：

- 对本地视频读取 FPS、分辨率、总帧数、时长

交付物：

- `ingest/media.py`

验收标准：

- 输入视频路径，能生成合法 `VideoSource`
- 元信息读取失败时返回明确错误

依赖：

- T2

### T4. 集成 PySceneDetect 粗切

目标：

- 跑第一阶段粗切
- 生成 `coarse_boundaries`

交付物：

- `detectors/pyscenedetect_runner.py`

固定要求：

- 使用 `ContentDetector`
- 使用 `AdaptiveDetector`
- 使用 `ThresholdDetector`

验收标准：

- 输入视频后能输出 coarse candidates
- detector evidence 可写入 manifest

依赖：

- T2
- T3
- 参考 `07-detector-integration-spec.md`

### T5. 实现 suspicious windows 生成

目标：

- 根据 coarse 结果生成 refinement 窗口

交付物：

- `detectors/suspicious_windows.py`

必须覆盖规则：

- coarse candidate 前后窗口
- 低置信度波动区
- 超长 scene 区间
- gradual suspect

验收标准：

- 能生成 `SuspiciousWindow[]`
- 支持窗口合并
- 默认参数与 spec 一致

依赖：

- T4

### T6. 集成 TransNetV2 refinement

目标：

- 对 suspicious windows 跑第二阶段检测

交付物：

- `detectors/transnetv2_runner.py`

验收标准：

- 可输入 `SuspiciousWindow[]`
- 可输出 refined candidates
- 模型不可用时能优雅降级

依赖：

- T5

### T7. 实现 fusion / decision

目标：

- 将 coarse / refined 结果合并为 `final_boundaries`

交付物：

- `fusion/decision.py`

必须覆盖规则：

- hard cut 保留
- gradual transition 优先
- 近邻去重
- merge collapse
- `recommended_cut_frame` 生成
- `confidence` 默认规则

验收标准：

- 能基于示例数据生成稳定 `final_boundaries`
- `source_boundary_ids` 继承正确

依赖：

- T4
- T6

### T8. 实现 analyze 主流程

目标：

- 将 ingest → coarse → suspicious → refine → fusion 串起来

交付物：

- `api.py`
- `cli.py` 中 `analyze` 命令

验收标准：

- 执行 `scene-workbench analyze input.mp4 --output manifest.json`
- 能落出合法 manifest

依赖：

- T3
- T4
- T5
- T6
- T7

---

## M2：Review Harness 与人工修正

### T9. 实现 manifest 读写

目标：

- 支持读取、保存、自动保存 manifest

交付物：

- `review/store.py`

验收标准：

- 能加载样例 manifest
- 能保存修改后的 manifest

依赖：

- T2

### T10. 实现 review action 核心逻辑

目标：

- 落地 `apply_review_action()`

交付物：

- `review/actions.py`

必须覆盖动作：

- `accept`
- `reject`
- `adjust`
- `merge`
- `insert`

验收标准：

- 每个动作都能正确更新 `final_boundaries`
- `review_actions` 追加正确
- `summary` 重算正确

依赖：

- T2
- T9
- 参考 `review-actions.example.md`

### T11. 实现 preview 辅助逻辑

目标：

- 为 review harness 提供边界前后关键帧索引或缩略图信息

交付物：

- `review/preview.py`

验收标准：

- 给定边界可返回前后关键帧
- gradual transition 可返回起始、中间、结束帧

依赖：

- T3
- T10

### T12. 实现最小 Web review harness

目标：

- 启动本地 Web 页面，支持浏览和修正边界

交付物：

- `web/app.py`
- 最小模板和静态资源

最小能力：

- 边界列表
- 边界预览
- evidence 展示
- 5 个 review action
- 自动保存

验收标准：

- 能打开本地页面
- 能对 manifest 做动作并保存

依赖：

- T9
- T10
- T11

### T13. 实现 review CLI 入口

目标：

- 将本地 Web review 流程接到 CLI

交付物：

- `cli.py` 中 `review` 命令

验收标准：

- 执行 `scene-workbench review manifest.json`
- 能启动本地 Web review

依赖：

- T12

---

## M3：导出、评估与收尾

### T14. 实现 JSON / cut list 导出

目标：

- 先实现最简单导出格式

交付物：

- `export/json_exporter.py`
- `export/cutlist_exporter.py`

验收标准：

- 能基于 `final_boundaries` 导出
- 默认只导出当前活动工作集

依赖：

- T10

### T15. 实现 EDL / FFmpeg 导出

目标：

- 支持下游剪辑与切片命令生成

交付物：

- `export/edl_exporter.py`
- `export/ffmpeg_exporter.py`

验收标准：

- 能生成最小可用 EDL
- 能生成 FFmpeg split 命令

依赖：

- T14

### T16. 实现 export CLI 入口

目标：

- 将导出能力接入 CLI

交付物：

- `cli.py` 中 `export` 命令

验收标准：

- `json`
- `cutlist`
- `edl`
- `ffmpeg`

这 4 种格式能从命令行导出

依赖：

- T14
- T15

### T17. 建立最小评估集

目标：

- 建立第一批验证样本

建议样本：

- 动画短片样本
- 微电影样本
- dissolve / fade / wipe 片段
- 闪白 / 强运动 / 特效片段

验收标准：

- 有一组固定输入视频
- 有最小人工标注或人工预期结果

依赖：

- 无

### T18. 跑第一轮基线评估

目标：

- 验证当前 V1 是否值得继续优化

指标：

- 漏切数
- 碎切数
- 人工修正次数
- 人工核对总时长

验收标准：

- 至少出一版基线报告
- 能支撑下一轮参数调整

依赖：

- T8
- T13
- T16
- T17

---

## 并行开发建议

适合并行的模块：

- T2 与 T1 后可并行准备 schema / 类型实现
- T4、T5、T6、T7 可前后串联，但不同人可先并行预研
- T10、T11、T12 可在 M1 接近完成时并行
- T14、T15、T16 可在 M2 后并行

不建议并行的部分：

- 在 `apply_review_action()` 未定稿前，不要先写复杂 review 前端状态逻辑
- 在 `final_boundaries` 规则未稳定前，不要先写复杂导出适配

---

## 当前开工建议

如果现在就开始，建议本周只做：

1. T1 建项目骨架
2. T2 落地核心数据模型
3. T3 视频元信息读取
4. T4 PySceneDetect 粗切
5. T5 suspicious windows

这样一周内就能把“检测主链路前半段”跑起来。

## 完成定义

可以认为 V1 进入“可试用”状态的最低标准是：

- 能生成 manifest
- 能在 Web 中审阅和修正
- 能导出至少一种下游格式
- 能跑一轮真实样本评估
