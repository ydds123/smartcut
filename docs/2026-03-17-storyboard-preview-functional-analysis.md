# 分镜预览页面功能分析报告

- 日期：2026-03-17
- 适用范围：`smartcut` 当前前后端实现
- 核心对象：`ReviewModal` 审核工作台及其后端支撑接口

## 1. 结论摘要

当前“分镜预览页面”本质上不是一个简单的预览弹窗，而是一个位于“场景检测”与“正式切分”之间的审核 Harness。

它承担的不是单纯展示职责，而是以下四类职责：

1. 承接算法输出：加载场景检测结果、用户草稿、已切分结果的回退数据。
2. 提供人工校验：通过视频、时间轴、镜头列表和逐镜头笔记，让用户判断切点是否合理。
3. 提供人工修正：支持增删切分点、局部高精度重算、整片重检。
4. 作为执行闸门：只有在审核页确认后，结果才进入正式切分或重新切分流程。

从产品语义上，当前名称“分镜预览”偏轻；从代码职责看，它更接近“分镜审核工作台”或“切分审核 Harness”。

## 2. 页面入口与挂载方式

当前主入口来自任务列表中的“预览分镜”按钮。

- 列表页入口与触发：
  - `frontend/src/components/task/TaskList.tsx`
  - `frontend/src/components/task/TaskListItem.tsx`
  - `frontend/src/components/task/TaskCard.tsx`
- 预览按钮显示条件：
  - `frontend/src/components/task/taskPreviewState.ts`
- 弹窗状态管理：
  - `frontend/src/stores/uiStore.ts`
- 页面常驻挂载：
  - `frontend/src/App.tsx`

审核工作台不是独立路由，而是由 `ReviewModal` 作为全屏固定层挂载在应用根节点下。

## 3. 页面整体布局

主页面实现位于：

- `frontend/src/components/review/ReviewModal.tsx`

页面采用三栏工作台结构：

1. 左栏：原视频预览 + 顶部工具条 + 时间轴编辑区
2. 中栏：镜头摘要列表 / 分镜缩略图列表
3. 右栏：拉片笔记面板

布局特点：

- 两条纵向分隔条支持拖拽调宽。
- 用户布局偏好会保存到 `localStorage`。
- 存在最小宽度限制，更偏向桌面审核场景，不是移动优先页面。

## 4. 前端功能清单

### 4.1 审核数据加载

打开页面后，会根据 `reviewTaskId` 拉取审核数据，主要包括：

- 检测结果 `detectionResult`
- 用户编辑后的分镜草稿 `userEditedScenes`
- 分镜笔记 `sceneReviewNotes`
- 当前任务状态

相关代码：

- `frontend/src/hooks/useTasks.ts`
- `frontend/src/services/taskService.ts`

### 4.2 原视频播放与播放控制

左栏支持原视频播放，并与审核状态联动。

能力包括：

- 播放 / 暂停
- 播放速率切换
- 跳转到指定时间
- 视频时间与播放头同步
- 视频加载失败处理

相关代码：

- `frontend/src/components/review/ReviewModal.tsx`
- `frontend/src/components/review/ReviewPlaybackControls.tsx`

### 4.3 时间轴工作区

时间轴工作区是分镜预览页的核心编辑面。

主组件：

- `frontend/src/components/review/ReviewTimelineWorkspace.tsx`

能力包括：

- 展示分镜块
- 展示场景内部关键帧 / 缩略图
- 展示播放头和时间刻度
- 时间轴缩放
- 视口滚动与自动定位
- 双击 / 点击定位播放头
- 删除边界
- 为当前播放位置增加边界

当前支持的编辑动作：

- 添加切分点
- 删除临近切分点
- 通过点击红色边界直接删除某条边界

### 4.4 镜头摘要列表

中栏为镜头摘要与浏览区。

主组件：

- `frontend/src/components/review/ReviewShotSummaryPanel.tsx`
- `frontend/src/components/shared/SceneListRail.tsx`

能力包括：

- 按镜头展示缩略图
- 展示起止时间
- 标记某镜头是否有笔记
- 选中某镜头后跳到对应播放位置
- 一键“定位当前镜头”

### 4.5 拉片笔记

右栏是以“当前分镜”为单位的笔记系统，而不是任务级单篇长文。

主组件：

- `frontend/src/components/review/ReviewNotesPanel.tsx`
- `frontend/src/components/review/reviewNotes.ts`
- `frontend/src/components/review/ReviewNotesImageExtension.tsx`

能力包括：

- 当前镜头范围提示
- 标题、加粗、斜体、列表、引用、分割线等富文本能力
- 链接插入
- 当前帧截图插入
- 截图节点反向定位到时间轴
- 自动保存
- 手动保存
- 保存状态反馈：已保存 / 保存中 / 保存失败

### 4.6 局部高精度处理

当前页面支持以当前播放头附近镜头为中心，触发一次局部高精度检测。

前端相关代码：

- `frontend/src/components/review/ReviewModal.tsx`
- `frontend/src/components/review/LocalPrecisionPreviewModal.tsx`
- `frontend/src/components/review/localPrecisionUtils.ts`

交互过程：

1. 根据当前播放头或选中镜头计算锚点镜头
2. 调用后端局部高精度预览接口
3. 展示“原方案 vs 建议方案”
4. 用户确认后把建议方案合并到当前分镜草稿

### 4.7 高级整片重检

当前页面支持打开高级参数弹窗，对整片重新检测并自动重新切分。

相关代码：

- `frontend/src/components/review/ReviewModal.tsx`
- `frontend/src/components/task/ProcessingConfigModal.tsx`
- `frontend/src/components/task/processingConfigSettings.ts`

该能力本质上是一个“临时重跑链路”：

1. 先发起一次 review 检测任务
2. review 完成后自动调用 approve 接口
3. 后续自动进入 split 阶段
4. 页面内部通过进度状态、轮询和 SSE 来跟踪阶段流转

### 4.8 确认切分与重新切分

顶部主按钮承担正式提交职责。

语义随任务状态变化：

- `REVIEW_PENDING` 时：确认并切分
- `TIMELINE_READY` 时：重新切分并覆盖

这说明页面已经不是只读预览，而是正式生产控制入口。

### 4.9 故事介绍入口

审核页头部内置“故事介绍”按钮，会联动故事简介 / 叙事分析弹窗。

相关代码：

- `frontend/src/components/review/StoryIntroModalHost.tsx`
- `frontend/src/components/review/StoryIntroModal.tsx`
- `frontend/src/components/review/StoryIntroMarkdown.tsx`

这部分不属于分镜编辑本体，但已经嵌入审核流程。

## 5. 页面中的核心交互与状态同步

### 5.1 播放头、视频、选中镜头三方联动

当前页面最重要的状态同步关系是：

- 视频当前时间
- 时间轴播放头位置
- 当前选中镜头索引

这些状态在 `ReviewModal` 中统一协调，保证用户在左、中、右三个面板之间切换时上下文一致。

### 5.2 分镜修改与笔记重映射

当用户增加或删除切分点时，当前镜头集合会变化。

页面会同步执行笔记重映射逻辑，避免原有镜头笔记直接丢失。

相关代码：

- `frontend/src/components/review/ReviewModal.tsx`
- `frontend/src/components/review/reviewNotes.ts`

### 5.3 自动保存与关闭拦截

笔记不是即时每次都写接口，而是：

1. 用户编辑后进入 `saving` 态
2. 延迟触发 autosave
3. 如果保存卡住，会触发补偿重试
4. 页面关闭前会先 flush 草稿
5. flush 失败则阻止关闭

这说明右栏并不是普通表单，而是工作台中的持久化编辑器。

### 5.4 审核态内的“再处理”能力

当前页不仅支持手改分镜，还支持两种重新计算方式：

- 局部高精度处理：只处理附近窗口
- 高级整片重检：重新检测并重新切分整片

这使得页面成为一个“人机协同修正层”，而不是算法结果的静态展示层。

## 6. 后端支撑能力

后端相关核心文件：

- `backend/app/api/tasks.py`
- `backend/app/schemas/task.py`
- `backend/app/models/models.py`
- `backend/app/services/review_notes.py`
- `backend/app/workers/video_tasks.py`

### 6.1 审核数据获取

接口：

- `GET /api/tasks/{task_id}/review-data`

职责：

- 返回场景检测结果
- 返回用户编辑后的场景草稿
- 返回按镜头对齐的笔记数据
- 返回当前审核态状态

### 6.2 审核数据保存

接口：

- `PUT /api/tasks/{task_id}/review-data`

支持写入：

- `scenes`
- `scene_review_notes`

后端校验点：

- `scenes` 必须按 `start_ms` 升序
- 相邻镜头不能重叠
- `end_ms` 必须大于 `start_ms`
- 某些状态下禁止编辑

### 6.3 局部高精度预览

接口：

- `POST /api/tasks/{task_id}/review/local-precision-preview`

职责：

- 以某个锚点镜头为中心，计算局部窗口
- 临时裁出一段子视频
- 以 precision 模式做同步检测
- 返回原始镜头和建议镜头的对比方案

### 6.4 审核确认并切分

接口：

- `POST /api/tasks/{task_id}/approve`

职责：

- 将任务从 `REVIEW_PENDING` 或 `TIMELINE_READY` 推入 `REVIEW_APPROVED`
- 写入 `reviewed_at`
- 入队切分任务

### 6.5 返回审核态

接口：

- `POST /api/tasks/{task_id}/return-to-review`

职责：

- 删除已切分产物
- 删除 `Scene` 表中的现有场景记录
- 将任务恢复到 `REVIEW_PENDING`

这说明后端已经原生支持“切完后再回到审核层重改”的闭环。

### 6.6 从时间轴结果重置审核稿

接口：

- `POST /api/tasks/{task_id}/review/reset-from-timeline`

职责：

- 把当前 `Scene` 表中的时间轴结果重新写回审核草稿 `user_edited_scenes`
- 避免用户重新编辑时镜头数量和已切分结果不一致

### 6.7 打开镜头目录

接口：

- `POST /api/tasks/{task_id}/scenes/{scene_id}/open-folder`

职责：

- 打开某个镜头切片对应的目录

该能力后端已具备，但当前审核页未暴露入口。

## 7. 任务状态流转

当前分镜预览页涉及的主要状态链路如下：

1. 上传完成后自动触发 review 检测
2. 任务进入 `DETECTING`
3. 检测结束进入 `REVIEW_PENDING`
4. 用户在审核页中查看、修改、补笔记
5. 用户点击确认后进入 `REVIEW_APPROVED`
6. 后端切分中进入 `SPLITTING`
7. 切分完成进入 `TIMELINE_READY`
8. 如需回退，调用 `return-to-review` 回到 `REVIEW_PENDING`

从这个状态链路可以看出，审核页是生产流程中的中间控制层，而不是旁路页面。

## 8. 当前遗留点与功能缺口

### 8.1 旧 Timeline 体系仍有残留

虽然当前主流程已切换到 `ReviewModal`，但旧版代码仍在仓库中：

- `frontend/src/components/timeline/TimelineModal.tsx`
- `frontend/src/components/error/TimelineModalErrorBoundary.tsx`

并且 `uiStore.ts` 中仍保留旧 timeline 相关状态，说明旧工作台尚未完全清理。

### 8.2 前端没有完整暴露后端已有能力

当前前端已封装但未在 `ReviewModal` 中显式暴露的能力包括：

- `return-to-review`
- `resetReviewFromTimeline`
- `openSceneFolder`

对应封装位于：

- `frontend/src/services/taskService.ts`

其中 `resetReviewFromTimeline` 和 `openSceneFolder` 已有 service，但当前审核页没有按钮。

### 8.3 页面命名与实际职责不一致

当前标题仍然是“分镜预览”，但页面职责已经覆盖：

- 预览
- 审核
- 修正
- 笔记
- 局部重算
- 整片重检
- 确认切分

从职责上看，它已经是完整审核工作台。

## 9. 建议

### 9.1 产品命名建议

建议将“分镜预览”调整为更符合职责的命名，例如：

- 分镜审核
- 分镜审核工作台
- 切分审核 Harness

### 9.2 前端补齐建议

建议在当前 `ReviewModal` 中补齐以下能力入口：

1. 返回审核态
2. 从当前时间轴重置审核稿
3. 打开镜头目录

这三项后端已经具备能力，前端主要是接线与交互设计问题。

### 9.3 代码治理建议

建议尽快明确是否彻底移除旧 `TimelineModal` 体系。

如果继续保留：

- 需要明确旧工作台与新审核工作台的职责边界

如果决定迁移完成：

- 应清理旧入口、旧 store 状态、旧错误边界与无主代码

## 10. 一句话定义

当前分镜预览页面可以定义为：

> 一个位于“场景检测结果”与“正式切分执行”之间的审核 Harness，用来把算法生成的候选分镜转化为可播放、可校验、可修正、可记录、可确认的生产输入。

