# 02 检测策略

## 目标

建立一套面向叙事视频的两阶段镜头边界检测策略：

- 第一阶段用轻量传统方法做全片粗切
- 第二阶段只在高风险区域做高精度 refinement

最终目标不是简单 detector 拼接，而是形成 transition-aware 的边界候选生成与裁决逻辑。

## 核心原则

- 第一阶段追求高召回，不追求最终精度
- 第二阶段只跑 suspicious windows，控制成本
- 输出必须保留边界区间、类型、置信度与 detector evidence

## 阶段一：PySceneDetect 粗切

第一阶段使用 PySceneDetect 进行快速、轻量、全片扫描。

建议组合使用：

- `ContentDetector`
- `AdaptiveDetector`
- `ThresholdDetector`

它的职责不是直接产出最终切点，而是产出：

- 粗切候选边界
- 分数波动信息
- 可疑 gradual transition 提示

## 阶段二：TransNetV2 精切

第二阶段只针对 suspicious windows 跑 TransNetV2，用于提高渐变类过渡的识别质量。

它主要服务于：

- dissolve
- fade in / fade out
- wipe
- 其他电影化或艺术化转场

## Suspicious Windows 生成规则

第二阶段不只对“已命中的候选边界”做 refinement，而是对“疑似有问题的局部区域”做 refinement。

建议最小规则集：

- 第一阶段候选边界前后窗口
- 第一阶段低置信度波动区
- 超长 scene 区间
- 怀疑 gradual transition 的局部片段

这一点的关键判断是：

**Refine suspicious windows，不是 refine only candidate cuts。**

## Fusion 思路

粗切和精切结果最终进入同一个 fusion / decision 层。

建议规则优先，暂不做复杂投票：

- hard cut 默认输出单点
- gradual transition 默认保留区间
- 近邻候选做去重和合并
- 置信度保留为结构化字段
- detector evidence 全量保留

## 在当前语境下的召回率与精确率

当前项目中的“召回率”与“精确率”应按人工核对语境理解：

- 召回率：人工认为应该标出来的镜头边界里，系统找到了多少
- 精确率：系统报出来的边界里，人工认可为合理切分的有多少

对应到问题：

- 漏切本质上是召回率问题
- 碎切本质上是精确率问题

## 单点 Cut 与 Transition 区间

内部 canonical representation 建议采用“transition 区间 + 类型”，而不是只保留单点 cut。

原因：

- hard cut 适合单点表达
- dissolve / fade / wipe 更适合区间表达
- review harness 需要看到真实转场区间
- 下游导出时仍可投影成单点时间戳

因此内部应保留：

- `start_frame`
- `end_frame`
- `recommended_cut_frame`
- `boundary_type`
- `confidence`
- `detector_evidence`

## 借鉴项目

`musicvideocutter` 值得借鉴的重点：

- detector orchestration
- 参数化配置
- 输出结构
- 后处理与导出链路

不建议直接复制它的最终裁决思路，因为当前项目更强调叙事视频下的 transition-aware 处理，而不仅是 detector ensemble 投票。

## 检测链路相关目录建议

围绕检测链路，建议优先形成这些模块：

- `ingest/`：视频元信息与输入上下文读取
- `detectors/`：PySceneDetect 粗切、TransNetV2 精切、suspicious windows 生成
- `fusion/`：粗切与精切结果融合、规则裁决

这些目录对应的是算法主链路，不应混入 review UI 或导出逻辑。

## 模块职责定义

### ingest

职责：

- 读取视频路径、FPS、分辨率、总帧数、时长
- 形成统一 `VideoSource`

### detectors

职责：

- 跑第一阶段粗切
- 生成 suspicious windows
- 跑第二阶段 refinement

### fusion

职责：

- 合并 coarse / refined 结果
- 统一输出边界对象
- 生成可进入 review harness 的工作集

## 实现顺序建议：M1 检测内核

M1 优先打通检测内核：

1. `ingest/media.py`
2. `detectors/pyscenedetect_runner.py`
3. `detectors/suspicious_windows.py`
4. `detectors/transnetv2_runner.py`
5. `fusion/decision.py`

完成标准：

- 能对单个本地视频输出 `manifest.json`
- 其中包含 `coarse_boundaries`、`suspicious_windows`、`refined_boundaries`、`final_boundaries`

## 哪些先 stub，哪些必须一次做对

可以先 stub：

- `transnetv2_runner.py`
  先返回固定结构，先验证主链路 I/O

必须一次做对：

- `BoundaryCandidate` 结构
- `frame` 作为内部主时基
- fusion 的职责边界
- `manifest.json` 的主字段布局

## 建议的最小技术选型

检测链路建议的最小技术选型：

- `PySceneDetect`
- `TransNetV2`
- `opencv-python` 或 `ffmpeg-python` 作为帧辅助能力
- Python 为核心实现语言
