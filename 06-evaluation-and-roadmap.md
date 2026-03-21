# 06 评估与路线图

## V1 评估目标

V1 的核心评估目标不是追求论文指标最高，而是证明：

- 系统能显著降低人工镜头校对成本
- 对动画短片和微电影这类叙事型视频有实际可用性

## 关键指标

建议同时记录三类指标：

### 算法层

- 边界召回率
- 边界精确率
- gradual transition 识别率

### 结构层

- 碎切数
- 漏切数
- gradual transition 被切成多个点的比例

### 人工成本层

- 每 20 分钟视频的人工修正次数
- 每 20 分钟视频的人工核对总时长
- 人工接受率

## 错误分类建议

建议至少区分这些错误：

- false split
- missed boundary
- wrong boundary type
- over-segmentation in gradual transition
- cut frame slightly early / late

## 评估集建议

V1 应该优先建立一个小而明确的评估集：

- 动画短片样本
- 微电影样本
- 具有 dissolve / fade / wipe 的片段
- 长镜头、闪白、强运动、特效等高风险片段

## 路线图

### Phase 1：最小闭环

- 本地视频输入
- 两阶段切分
- review harness
- 人工修正
- 标准导出

### Phase 2：能力层

- Python API
- CLI 稳定化
- schema 稳定化
- 更系统的配置与调参

### Phase 3：分发层

- 插件节点
- SDK
- 云端处理
- 工作流平台集成

## 当前明确延后

这些问题暂时不进入 V1：

- 云端抓取与下载
- 平台化协作
- 自动叙事段落划分
- 大规模任务编排
- 多宿主插件适配

## 当前开放问题

仍需在后续阶段继续验证的问题包括：

- 不同类型 gradual transition 的最优 fusion 规则
- review harness 中“调整”和“合并”的最低交互成本
- `detector_evidence` 的展示粒度
- 导出结果与下游剪辑流程的适配深度

## 判断标准

如果 V1 能做到下面这件事，就说明方向成立：

**把 20 分钟叙事视频的镜头校对，从重看全片，变成确认候选。**

## 为什么 manifest + review_actions 结构有利于后续评估

保留 `manifest + review_actions` 的结构，对后续评估和迭代有三个直接好处：

- 可以区分算法原始输出与人工最终结果
- 可以回放每一次人工修正动作
- 可以统计哪些类型的边界最容易被调整、合并、插入或拒绝

这意味着后续评估不只看最终边界结果，还能看“人工怎么改了它”，从而支持：

- detector 调参
- fusion 规则优化
- review harness 交互优化
