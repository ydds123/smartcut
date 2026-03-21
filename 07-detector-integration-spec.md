# 07 Detector Integration Spec

## 目标与边界

本文档只覆盖检测链路的实现规范，回答这四个问题：

- `PySceneDetect` 怎么接入
- `suspicious windows` 怎么生成
- `TransNetV2` 怎么接入
- `fusion v1` 怎么做裁决

本文档不覆盖：

- review harness 页面交互
- 导出格式实现
- 云端抓取、插件、SDK 分发

## 检测链路总流程

```text
视频输入
→ 读取元信息
→ PySceneDetect 粗切
→ suspicious windows 生成
→ TransNetV2 精切
→ fusion 裁决
→ 写入 manifest
```

## 输入与主时基约定

- 输入对象：本地视频文件路径
- 内部主时基：`frame`
- 时间戳仅用于展示和导出
- 所有 detector 输出都必须映射到统一的 `BoundaryCandidate`

## PySceneDetect 集成规范

### 使用的 detector

第一版固定使用：

- `ContentDetector`
- `AdaptiveDetector`
- `ThresholdDetector`

### 职责分工

- `ContentDetector`
  用于快速捕捉明显的 hard cut 候选
- `AdaptiveDetector`
  用于抑制剧烈运动导致的误触发，并补充稳定性判断
- `ThresholdDetector`
  用于发现 fade in / fade out 这类亮度主导的边界

### 输入

- `video_path`
- `coarse_detection` 配置

### 输出

PySceneDetect 层输出两类内容：

1. `coarse_boundaries`
2. detector-level evidence 与 score 信号

每个命中的候选边界都要映射成 `BoundaryCandidate`，但在这一层：

- `review_state` 默认为 `unreviewed`
- `source_boundary_ids` 可为空
- `boundary_type` 初始可为 `hard_cut` 或 `unknown`

### 默认参数入口

推荐放在 `config.coarse_detection`：

- `content_threshold`
- `adaptive_threshold`
- `min_scene_len`

### 失败策略

如果 PySceneDetect 运行失败：

- 终止本次检测主流程
- 返回明确错误
- 不允许“无 coarse 结果继续 refinement”

原因：第一阶段是第二阶段的候选来源。

## suspicious windows 生成规范

### 目标

第二阶段不跑全片，只跑高风险区域。

### 生成规则

最小规则集固定为：

- 第一阶段候选边界前后窗口
- 第一阶段低置信度波动区
- 超长 scene 区间
- 怀疑 gradual transition 的局部片段

### 默认参数表

第一版默认参数建议直接冻结为：

- `window_padding_frames = 12`
- `merge_gap_frames = 6`
- `long_scene_threshold_frames = 240`
- `max_window_frames = 96`

说明：

- `window_padding_frames = 12`
  表示对 coarse candidate 前后各扩 12 帧，形成 refinement 窗口
- `merge_gap_frames = 6`
  表示两个相邻窗口或候选间隔小于等于 6 帧时，视为同一事件的候选
- `long_scene_threshold_frames = 240`
  对 24fps 素材约等于 10 秒；超过该长度的 scene 默认进入可疑窗口生成逻辑
- `max_window_frames = 96`
  用于防止 refinement 窗口无限扩张

### 规则解释

#### A. coarse candidate 周边窗口

对于每个 coarse boundary：

- 左右各加 `window_padding_frames`
- 形成一个局部 refinement 窗口

#### B. 低置信度波动区

如果 detector 有明显波动但未形成稳定 hard cut：

- 记录为 `low_confidence`
- 进入 suspicious windows

#### C. 超长 scene

当某一 scene 区间长度超过配置阈值时：

- 视为可能漏切
- 划入 suspicious windows

#### D. gradual suspect

当 `ThresholdDetector` 或多 detector 弱命中聚集时：

- 标为 `gradual_suspect`

### 窗口合并规则

如果两个 suspicious windows 重叠或间隔小于等于 `merge_gap_frames`：

- 合并成一个更大的窗口

### 输出对象

每个窗口输出：

- `id`
- `start_frame`
- `end_frame`
- `reason`
- `source_boundary_ids`

## TransNetV2 集成规范

### 使用方式

TransNetV2 只处理 `suspicious_windows`

### 输入

- `video_path`
- `SuspiciousWindow[]`
- `refinement` 配置

### 输出

对每个窗口输出一个或多个 refined candidates：

- hard cut 候选
- gradual transition 区间
- score

并映射到统一 `BoundaryCandidate`

### 字段映射

- `boundary_type`
  允许为：
  - `hard_cut`
  - `dissolve`
  - `fade_in`
  - `fade_out`
  - `wipe`
  - `unknown`
- `detector_evidence.transnetv2.score`
  保存模型分数
- `detector_evidence.transnetv2.window_id`
  保存来源窗口

### 失败策略

如果 TransNetV2 不可用或运行失败：

- 跳过 refinement
- 保留 coarse 输出
- 在日志或 manifest 外层记录 warning

也就是说：

**fail soft，而不是 fail closed。**

## fusion v1 规则

### 目标

把 coarse 与 refined 结果统一成 `final_boundaries`

### 总原则

- hard cut 优先单点输出
- gradual transition 优先保留区间
- refined 结果对 suspicious windows 有更高裁决权
- detector evidence 必须保留

### 规则 1：hard cut 保留

如果 coarse 和 refined 都支持某个 hard cut，且位置接近：

- 合并为一个 final boundary
- `recommended_cut_frame` 取 refined 优先，否则取 coarse

### 规则 2：gradual transition 优先

如果 refined 明确给出 gradual transition 区间：

- 优先保留区间
- 附近 coarse 的多个 hard-cut spike 应 collapse 到该区间

### 规则 3：近邻去重

如果两个候选边界间隔小于等于 `merge_gap_frames`：

- 默认视为同一事件
- 由 refined 结果优先裁决

### 规则 4：recommended_cut_frame 生成

- hard cut：等于边界帧
- gradual transition：默认取区间中点
- 若 refined 提供更明确推荐点，则 refined 优先

### 规则 5：confidence 生成

第一版建议采用简单规则：

- 有 refined 支持时，以 refined score 为主
- 只有 coarse 时，使用 coarse 分数映射到固定默认区间
- merge 后取更高置信的一侧，或按规则上调

第一版具体实现建议固定为：

- refined gradual transition：
  `confidence = transnetv2.score`
- refined hard cut：
  `confidence = transnetv2.score`
- coarse only，且 `ContentDetector.triggered = true`：
  `confidence = 0.60`
- coarse only，且 `AdaptiveDetector.triggered = true`：
  `confidence = max(confidence, 0.55)`
- coarse only，且 `ThresholdDetector.triggered = true`：
  `confidence = max(confidence, 0.65)`
- merge 形成的 gradual transition：
  `confidence = max(child_confidences, refined_score if exists else 0.70)`

这套规则的目标不是统计意义上最优，而是先保证：

- 有确定默认行为
- 前后端展示稳定
- 后续调参时有统一基线

### 规则 6：source_boundary_ids 继承

- hard cut：继承对应 coarse / refined 来源 ID
- merge：取并集
- insert：为空列表

## manifest 写入约定

### coarse_boundaries

由 PySceneDetect 层生成

### suspicious_windows

由 suspicious window 生成器生成

### refined_boundaries

由 TransNetV2 层生成

### final_boundaries

由 fusion 层生成

## 失败模式与降级策略

### 视频元信息读取失败

- 直接终止流程
- 不进入 detector

### PySceneDetect 失败

- 终止流程
- 返回检测失败错误

### TransNetV2 失败

- 记录 warning
- 继续保留 coarse 输出

### 单 detector 无结果

- 不视为失败
- 只要整体 coarse / refined 流程还能产出候选，就继续

## 测试场景

集成测试至少覆盖：

- clear hard cut
- dissolve
- fade in / fade out
- flash / lighting false positive
- long scene with missed candidate
- overlapping suspicious windows

## 默认实现决策

为了避免开发期继续反复讨论，第一版固定这些默认选择：

- 第一阶段固定使用 `ContentDetector + AdaptiveDetector + ThresholdDetector`
- 第二阶段固定只跑 suspicious windows
- 内部以 `frame` 为主时基
- gradual transition 内部保存区间
- hard cut 内部允许单帧区间
- TransNetV2 不可用时继续输出 coarse 结果
- fusion v1 先用规则，不做加权投票
