# 03 边界模型与 Manifest

## 目标

为算法、前端、CLI、导出层定义统一的数据契约，避免各模块围绕不同的中间格式开发。

## 核心对象

### BoundaryCandidate

边界候选对象，是全系统的核心数据单元。

建议字段：

- `id`
- `start_frame`
- `end_frame`
- `recommended_cut_frame`
- `boundary_type`
- `confidence`
- `review_state`
- `source_boundary_ids`
- `detector_evidence`
- `notes`

其中：

- `hard_cut` 可表现为单帧区间
- gradual transition 必须保留真实区间
- `recommended_cut_frame` 用于兼容只接受单点的导出场景

### SuspiciousWindow

表示二阶段 refinement 的局部分析区间。

建议字段：

- `id`
- `start_frame`
- `end_frame`
- `reason`
- `source_boundary_ids`

### ReviewAction

表示人工修正动作的结构化记录。

建议支持动作：

- `accept`
- `reject`
- `adjust`
- `merge`
- `insert`

### ProjectManifest

表示一个视频从检测到审阅再到导出的完整中间结果。

建议结构：

- `video`
- `config`
- `coarse_boundaries`
- `suspicious_windows`
- `refined_boundaries`
- `final_boundaries`
- `review_actions`
- `summary`

## 分层原则

### coarse_boundaries

只记录第一阶段算法结果，作为只读证据层。

### refined_boundaries

只记录第二阶段 refinement 结果，作为只读证据层。

### final_boundaries

当前可审阅、可导出、可作为工作集的边界集合。

### review_actions

完整记录人工如何把算法候选修正成最终结果。

## Review 行为约定

关键约定：

- `coarse_boundaries` 和 `refined_boundaries` 永远不被人工动作直接修改
- 人工动作只作用于 `final_boundaries`
- `review_actions` 永远作为审计日志追加，不覆盖
- `source_boundary_ids` 用于保留血缘关系

## 为什么内部保留区间和类型

本项目内部不应只保留单点 cut，原因如下：

- gradual transition 不是瞬时事件
- review harness 需要可视化真实过渡范围
- 后续调参与错误分析需要知道边界区间与类型
- 对外导出时仍可以投影成时间戳和 EDL

## Manifest 的角色

Manifest 是系统中心，而不是附属导出文件。

它承担这些职责：

- 算法输出的统一承载体
- review harness 的数据源
- 人工修正后的状态落盘载体
- 导出层的统一输入
- 后续调参与错误分析的基础数据

## 第一版 manifest.json 完整示例

完整样例文件不直接嵌入主文档，统一放在：

- [`manifest.v1.example.json`](E:/上虞园区数据对接/处理视频资料/examples/manifest.v1.example.json)
- [`manifest.v1.schema.json`](E:/上虞园区数据对接/处理视频资料/examples/manifest.v1.schema.json)

该样例覆盖：

- hard cut
- dissolve
- 人工调整
- 合并
- 插入
- 拒绝

## TypeScript 类型定义

前端 / Node 侧参考类型定义统一放在：

- [`manifest.types.example.ts`](E:/上虞园区数据对接/处理视频资料/examples/manifest.types.example.ts)

该文件包含：

- `BoundaryType`
- `ReviewState`
- `ReviewActionType`
- `VideoSource`
- `BoundaryCandidate`
- `SuspiciousWindow`
- `ReviewAction`
- `ProjectManifest`

## Python Pydantic 模型定义

Python 侧参考模型统一放在：

- [`manifest.models.example.py`](E:/上虞园区数据对接/处理视频资料/examples/manifest.models.example.py)

要求：

- 使用 Pydantic v2
- JSON 字段名与 manifest 示例保持 1:1 一致

## JSON Schema

JSON Schema 统一放在：

- [`manifest.v1.schema.json`](E:/上虞园区数据对接/处理视频资料/examples/manifest.v1.schema.json)

约定：

- 根对象用于校验 `ProjectManifest`
- `$defs.ReviewActionCommand` 用于校验前端发往后端的动作命令

## apply_review_action() 的职责定义

`apply_review_action()` 的职责是：

- 接收当前 `ProjectManifest`
- 接收一个人工操作命令
- 更新 `final_boundaries`
- 追加一条 `review_actions`
- 重算 `summary`
- 返回新的 manifest

重要约定：

- 不直接修改 `coarse_boundaries`
- 不直接修改 `refined_boundaries`
- 人工动作只作用于 `final_boundaries`

## 输入命令对象：ReviewActionCommand

前端发给后端的输入命令对象，建议命名为：

- `ReviewActionCommand`

它和最终落盘的 `ReviewAction` 不是同一个对象。

前者是输入命令，后者是审计日志。

## 核心行为约定

建议明确写死以下行为约定：

- `final_boundaries` 是当前工作集
- `review_actions` 是完整审计日志
- `source_boundary_ids` 表示血缘关系，不表示当前可编辑目标
- `review_actions.target_boundary_ids` 表示**动作发生当时**工作集中的边界 ID；如果某个边界随后被 `merge` 或 `reject` 移出工作集，它可以不再出现在最终 manifest 的 `final_boundaries` 快照中
- 所有内部逻辑以 `frame` 为主，不以浮点秒为主

## 每个动作的行为规范

主文档中只保留规范摘要：

- `accept`：确认当前边界有效
- `reject`：从当前工作集移除边界
- `adjust`：人工调整帧位置
- `merge`：把多个边界合并成一个新边界
- `insert`：手动插入漏切边界

详细的请求、响应、伪代码样例统一放在：

- [`review-actions.example.md`](E:/上虞园区数据对接/处理视频资料/examples/review-actions.example.md)

## recompute_summary() 规则

`recompute_summary()` 负责重算：

- coarse / refined / final 数量
- accepted / adjusted / merged / inserted 数量
- rejected 统计

其中：

- `rejected` 建议来自 `review_actions`
- 当前活动工作集状态来自 `final_boundaries`

## 建议

后续所有前后端并行开发都应围绕同一版 manifest schema 展开，避免各自临时定义中间结构。
