# 04 Review Harness

## 一句话定义

分镜预览是视频切分流程中的 Harness：它把算法生成的候选分镜转化为可视化、可校验、可修正、可确认的中间层。

## 为什么它是核心

本项目的核心价值不是“给出一个切点列表”，而是让人工不必从头重看全片，只需要对候选边界进行确认和修正。

因此，review harness 不是附属 UI，而是：

- 算法结果到可用结果的桥梁
- 人工判断进入系统的结构化入口
- 后续数据闭环与调参的基础

## 最小页面结构

### 左侧：边界列表

显示：

- 边界 ID
- 时间范围
- `boundary_type`
- `confidence`
- `review_state`

支持按未审核、低置信度、时间顺序排序。

### 中间：预览区

显示：

- 当前边界前后关键帧
- gradual transition 的起始帧、中间帧、结束帧
- 推荐切点
- 邻近上下文帧

### 右侧：证据区

显示：

- PySceneDetect 哪个 detector 命中
- score
- TransNetV2 score
- suspicious window reason

## 最小交互动作

V1 只做五个动作：

- `accept`
- `reject`
- `adjust`
- `merge`
- `insert`

这五个动作已经足够覆盖：

- 直接接受
- 删除碎切
- 微调边界
- 把多个误碎切合并成一个 gradual transition
- 手动补漏切

## 最小交互流

建议流程：

```text
打开 manifest
→ 定位到第一个 unreviewed boundary
→ 查看当前边界与证据
→ 执行 accept / reject / adjust / merge / insert
→ 自动保存
→ 跳转下一个未审核边界
→ 审完后导出
```

## 状态保存

建议默认自动保存：

- 每次操作后立刻写回 manifest
- 中途中断后可继续恢复
- `review_actions` 全量保留操作历史

## 哪些动作由前端发 command，哪些由后端落日志

建议前后端职责明确分离：

### 前端负责

- 基于当前 manifest 发起 `ReviewActionCommand`
- 不直接本地篡改 `final_boundaries`
- 接收后端返回的新 manifest 并刷新 UI

### 后端负责

- 校验命令是否合法
- 真正修改 `final_boundaries`
- 生成 `ReviewAction`
- 追加审计日志
- 重算 `summary`
- 返回新的 manifest

这样能保证：

- 行为可追踪
- 状态更新一致
- 后续容易做 undo/redo 与回放

## V1 不做

V1 的 harness 暂不做：

- 复杂时间轴编辑器
- 多轨道播放控制
- 协作审阅
- 云端任务面板
- 大规模批量审核

## 成功标准

Review harness 成功的标准不是界面炫，而是：

- 算法结果看得懂
- 人工确认快
- 修正动作语义清晰
- 修改可追踪
