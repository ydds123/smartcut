# 09 Issue 任务卡

## 说明

本文档将 [`08-executable-task-list.md`](E:/上虞园区数据对接/处理视频资料/08-executable-task-list.md) 中的里程碑任务重组为可直接建 issue 的中等粒度任务卡。

每张卡都包含：

- 所属里程碑
- 目标
- 产出物
- 输入/依赖
- 写入范围 / ownership
- 验收标准
- 风险与注意事项

所有任务卡默认以这些资料为依据：

- [`03-boundary-model-and-manifest.md`](E:/上虞园区数据对接/处理视频资料/03-boundary-model-and-manifest.md)
- [`05-interfaces-and-delivery.md`](E:/上虞园区数据对接/处理视频资料/05-interfaces-and-delivery.md)
- [`07-detector-integration-spec.md`](E:/上虞园区数据对接/处理视频资料/07-detector-integration-spec.md)
- [`examples/`](E:/上虞园区数据对接/处理视频资料/examples)

---

## ISSUE-01 项目骨架与依赖初始化

- 所属里程碑：M1
- 目标：创建 Python 项目骨架、CLI 入口和测试目录
- 产出物：
  - `pyproject.toml`
  - `src/scene_workbench/`
  - `tests/`
- 输入/依赖：
  - [`05-interfaces-and-delivery.md`](E:/上虞园区数据对接/处理视频资料/05-interfaces-and-delivery.md)
- 写入范围 / ownership：
  - `pyproject.toml`
  - `src/scene_workbench/__init__.py`
  - `src/scene_workbench/cli.py`
  - `tests/`
- 验收标准：
  - 项目可安装依赖
  - CLI 入口可执行
- 风险与注意事项：
  - 不要提前写 detector 逻辑

## ISSUE-02 Manifest / Config / ReviewAction 数据模型落地

- 所属里程碑：M1
- 目标：将 manifest 契约正式实现为 Python 模型
- 产出物：
  - `models.py`
  - `config.py`
- 输入/依赖：
  - [`03-boundary-model-and-manifest.md`](E:/上虞园区数据对接/处理视频资料/03-boundary-model-and-manifest.md)
  - [`manifest.v1.schema.json`](E:/上虞园区数据对接/处理视频资料/examples/manifest.v1.schema.json)
  - [`manifest.models.example.py`](E:/上虞园区数据对接/处理视频资料/examples/manifest.models.example.py)
- 写入范围 / ownership：
  - `src/scene_workbench/models.py`
  - `src/scene_workbench/config.py`
- 验收标准：
  - 样例 manifest 可反序列化
  - `ReviewActionCommand` 明确定义
- 风险与注意事项：
  - 不要自行改字段名

## ISSUE-03 视频元信息读取与输入标准化

- 所属里程碑：M1
- 目标：实现本地视频元信息读取
- 产出物：
  - `ingest/media.py`
- 输入/依赖：
  - `ISSUE-02`
- 写入范围 / ownership：
  - `src/scene_workbench/ingest/media.py`
- 验收标准：
  - 输入视频路径能得到合法 `VideoSource`
  - 失败时返回清晰错误
- 风险与注意事项：
  - 当前只支持本地文件，不处理 URL 下载

## ISSUE-04 PySceneDetect 粗切集成

- 所属里程碑：M1
- 目标：实现第一阶段粗切
- 产出物：
  - `detectors/pyscenedetect_runner.py`
- 输入/依赖：
  - `ISSUE-02`
  - `ISSUE-03`
  - [`07-detector-integration-spec.md`](E:/上虞园区数据对接/处理视频资料/07-detector-integration-spec.md)
- 写入范围 / ownership：
  - `src/scene_workbench/detectors/pyscenedetect_runner.py`
- 验收标准：
  - 支持 `ContentDetector`
  - 支持 `AdaptiveDetector`
  - 支持 `ThresholdDetector`
  - 能输出 `coarse_boundaries`
- 风险与注意事项：
  - detector evidence 必须完整保留

## ISSUE-05 suspicious windows 生成

- 所属里程碑：M1
- 目标：根据 coarse 结果生成 refinement 窗口
- 产出物：
  - `detectors/suspicious_windows.py`
- 输入/依赖：
  - `ISSUE-04`
- 写入范围 / ownership：
  - `src/scene_workbench/detectors/suspicious_windows.py`
- 验收标准：
  - 覆盖 candidate 周边、低置信度、超长 scene、gradual suspect
  - 支持窗口合并
- 风险与注意事项：
  - 参数使用文档默认值，先不要自行发散

## ISSUE-06 TransNetV2 refinement 集成

- 所属里程碑：M1
- 目标：实现第二阶段 refinement
- 产出物：
  - `detectors/transnetv2_runner.py`
- 输入/依赖：
  - `ISSUE-05`
- 写入范围 / ownership：
  - `src/scene_workbench/detectors/transnetv2_runner.py`
- 验收标准：
  - 输入 `SuspiciousWindow[]`
  - 输出 refined candidates
  - 模型不可用时优雅降级
- 风险与注意事项：
  - 第一版可先 stub

## ISSUE-07 fusion / decision 实现

- 所属里程碑：M1
- 目标：实现 coarse / refined → final 的裁决逻辑
- 产出物：
  - `fusion/decision.py`
- 输入/依赖：
  - `ISSUE-04`
  - `ISSUE-06`
- 写入范围 / ownership：
  - `src/scene_workbench/fusion/`
- 验收标准：
  - hard cut 保留
  - gradual transition 优先
  - 近邻去重
  - confidence 默认规则生效
- 风险与注意事项：
  - `source_boundary_ids` 继承逻辑必须正确

## ISSUE-08 analyze API + CLI 打通

- 所属里程碑：M1
- 目标：把检测主链路串起来
- 产出物：
  - `api.py`
  - `cli.py` 中 `analyze`
- 输入/依赖：
  - `ISSUE-03`
  - `ISSUE-04`
  - `ISSUE-05`
  - `ISSUE-06`
  - `ISSUE-07`
- 写入范围 / ownership：
  - `src/scene_workbench/api.py`
  - `src/scene_workbench/cli.py`
- 验收标准：
  - 能生成合法 manifest
- 风险与注意事项：
  - `manifest.v1.schema.json` 必须作为联调基准

## ISSUE-09 manifest 读写与 apply_review_action 落地

- 所属里程碑：M2
- 目标：实现 manifest 状态读写与动作更新
- 产出物：
  - `review/store.py`
  - `review/actions.py`
- 输入/依赖：
  - `ISSUE-02`
  - [`review-actions.example.md`](E:/上虞园区数据对接/处理视频资料/examples/review-actions.example.md)
- 写入范围 / ownership：
  - `src/scene_workbench/review/store.py`
  - `src/scene_workbench/review/actions.py`
- 验收标准：
  - `accept / reject / adjust / merge / insert` 都能生效
  - `summary` 能重算
- 风险与注意事项：
  - 必须遵守当前工作集语义

## ISSUE-10 preview 辅助与最小 Web review harness

- 所属里程碑：M2
- 目标：实现最小可用 review harness
- 产出物：
  - `review/preview.py`
  - `web/app.py`
  - 最小模板与静态资源
- 输入/依赖：
  - `ISSUE-03`
  - `ISSUE-09`
  - [`04-review-harness.md`](E:/上虞园区数据对接/处理视频资料/04-review-harness.md)
- 写入范围 / ownership：
  - `src/scene_workbench/review/preview.py`
  - `src/scene_workbench/web/`
- 验收标准：
  - 能浏览边界
  - 能展示 evidence
  - 能执行 5 种动作
- 风险与注意事项：
  - V1 不做复杂时间轴

## ISSUE-11 review CLI 入口与本地 review 流程

- 所属里程碑：M2
- 目标：把 review harness 接到 CLI
- 产出物：
  - `cli.py` 中 `review`
- 输入/依赖：
  - `ISSUE-10`
- 写入范围 / ownership：
  - `src/scene_workbench/cli.py`
- 验收标准：
  - `scene-workbench review manifest.json` 可启动本地 review
- 风险与注意事项：
  - 只做本地 Web review

## ISSUE-12 JSON / cutlist / EDL / ffmpeg 导出

- 所属里程碑：M3
- 目标：实现标准导出链路
- 产出物：
  - `export/json_exporter.py`
  - `export/cutlist_exporter.py`
  - `export/edl_exporter.py`
  - `export/ffmpeg_exporter.py`
  - `cli.py` 中 `export`
- 输入/依赖：
  - `ISSUE-09`
  - `ISSUE-11`
- 写入范围 / ownership：
  - `src/scene_workbench/export/`
  - `src/scene_workbench/cli.py`
- 验收标准：
  - `json / cutlist / edl / ffmpeg` 四种格式可导出
- 风险与注意事项：
  - 只基于 `final_boundaries` 导出

## ISSUE-13 最小评估集建立

- 所属里程碑：M3
- 目标：建立第一批固定评估样本
- 产出物：
  - 评估样本清单
  - 最小人工标注或预期结果
- 输入/依赖：
  - [`06-evaluation-and-roadmap.md`](E:/上虞园区数据对接/处理视频资料/06-evaluation-and-roadmap.md)
- 写入范围 / ownership：
  - `评估样本目录`
  - `评估说明文档`
- 验收标准：
  - 至少覆盖 hard cut、dissolve、fade、flash、长镜头
- 风险与注意事项：
  - 当前先做小样本，不做大规模 benchmark

## ISSUE-14 第一轮基线评估与结果记录

- 所属里程碑：M3
- 目标：验证当前 V1 的可用性
- 产出物：
  - 第一轮评估记录
  - 基线指标
- 输入/依赖：
  - `ISSUE-08`
  - `ISSUE-11`
  - `ISSUE-12`
  - `ISSUE-13`
- 写入范围 / ownership：
  - `评估结果文档`
  - `必要的统计输出`
- 验收标准：
  - 至少输出：
    - 漏切数
    - 碎切数
    - 人工修正次数
    - 人工核对总时长
- 风险与注意事项：
  - 第一轮目标是验证方向，不是追求指标最优
