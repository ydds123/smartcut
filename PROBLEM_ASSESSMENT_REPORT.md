# SmartCut 问题评估报告

**测试日期：** 2026-02-19
**测试工具：** Browser Skill (Playwright)
**测试环境：** 前端 (localhost:5173) + 后端 (localhost:8000)

---

## ✅ 测试通过项

### 1. 前端服务可访问性
- ✅ http://localhost:5173 正常加载
- ✅ 页面标题："SmartCut - 智能拉片工具"
- ✅ 无 console 错误
- ✅ 无失败的 network 请求

### 2. 后端服务可访问性
- ✅ http://localhost:8000 API 响应正常
- ✅ 任务列表端点正常工作
- ✅ 任务详情端点正常工作
- ✅ 场景数据端点正常工作

---

## 🔴 发现的问题

### 问题 1：缩略图生成失败 [CRITICAL]

**问题描述：**
- 任务显示 57 个场景，但只生成了 1 个缩略图文件
- API 返回的缩略图路径正确，但文件实际不存在
- 导致 Timeline Modal 中无法显示场景缩略图

**验证结果：**
```bash
# 数据库中记录的场景数：57
# API 返回的场景数：57
# 实际生成的视频文件：57 个 ✅
# 实际生成的缩略图文件：1 个 ❌
```

**文件系统验证：**
```
backend/data/tasks/f1ff5c8f-0317-4e13-8704-0b34afd038ed/scenes/
├── scene_000.mp4        ✅ 存在
├── scene_000_thumb.jpg  ✅ 存在
├── scene_001.mp4        ✅ 存在
├── scene_001_thumb.jpg  ❌ 不存在
├── scene_002.mp4        ✅ 存在
├── scene_002_thumb.jpg  ❌ 不存在
...
├── scene_056.mp4        ✅ 存在
└── scene_056_thumb.jpg  ❌ 不存在
```

**根因分析：**
1. `video_processor.py` 中的 `generate_thumbnail()` 函数在第一次调用后可能失败
2. 可能原因：
   - FFmpeg 处理超时（代码中设置 5 秒超时）
   - FFmpeg 进程卡死
   - 文件系统权限问题
   - 内存不足

**影响范围：**
- Timeline Modal 无法显示场景预览
- 用户体验严重受损
- 核心功能不可用

**优先级：** 🔴 P0 - 最高优先级

---

### 问题 2：Timeline Modal 组件错误 [HIGH]

**问题描述：**
- Console 日志显示 `TimelineModal` 组件发生错误
- 错误信息："An error occurred in the <TimelineModal> component"
- Modal 无法正确显示场景内容

**Console 错误日志：**
```
⚠️ [12:52:27 PM] An error occurred in the <TimelineModal> component.
Consider adding an error boundary to your tree to customize error handling behavior.
```

**根因分析：**
1. 缩略图加载失败导致 React 组件崩溃
2. 组件没有正确的错误处理
3. 缺少 Error Boundary

**影响范围：**
- 用户无法查看处理结果
- Modal 打开后显示错误或空白

**优先级：** 🔴 P0 - 最高优先级

---

### 问题 3：Modal 关闭功能不可用 [MEDIUM]

**问题描述：**
- Modal 打开后无法通过点击关闭按钮关闭
- ESC 键可以关闭（已验证）
- 点击 Modal 外部区域无法关闭

**根因分析：**
1. z-index 层级问题
2. 事件监听器未正确绑定
3. 背景遮罩元素可点击区域太小

**影响范围：**
- 用户需要知道按 ESC 才能关闭
- 移动端用户体验差（没有 ESC 键）

**优先级：** 🟡 P2 - 中等优先级

---

## ✅ 未发现问题的功能

### Toast 通知系统
- ✅ 未发现明显样式问题
- ✅ 未发现层级遮挡问题
- ⚠️ 由于 Modal 问题，无法在 Modal 打开时验证 Toast 显示

### 音频提示系统
- ✅ 代码逻辑正确
- ⚠️ 浏览器可能阻止自动播放（需要用户交互）

---

## 修复建议

### 修复 1：缩略图生成问题 [P0]

**方案 A：增加错误处理和日志**
```python
# video_processor.py
def generate_thumbnail(self, video_file: str, output_file: str, ...) -> bool:
    # 添加详细日志
    logger.debug(f"开始生成缩略图: {video_file} -> {output_file}")

    # 增加超时时间
    timeout = 10  # 从 5 秒增加到 10 秒

    # 添加更详细的错误处理
    for attempt in range(max_retries):
        try:
            # ... 现有代码 ...
            logger.debug(f"缩略图生成成功: {output_file}")
            return True
        except subprocess.TimeoutExpired:
            logger.warning(f"缩略图生成超时 (尝试 {attempt + 1}/{max_retries}): {output_file}")
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg 错误: {e.stderr}")
```

**方案 B：并行生成缩略图**
```python
from concurrent.futures import ThreadPoolExecutor

def generate_thumbnails_parallel(self, output_files, scenes):
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []
        for i, video_file in enumerate(output_files):
            future = executor.submit(self.generate_thumbnail, ...)
            futures.append(future)

        results = [f.result() for f in futures]
    return results
```

**方案 C：降级方案**
```python
# 如果缩略图生成失败，使用默认占位图
if not success:
    thumbnail_path = "/placeholders/scene-thumbnail.jpg"
```

---

### 修复 2：Timeline Modal 错误处理 [P0]

**添加 Error Boundary：**
```typescript
// components/ErrorBoundary.tsx
class TimelineModalErrorBoundary extends React.Component {
  componentDidCatch(error, errorInfo) {
    console.error('TimelineModal Error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-message">
          场景加载失败，请稍后重试
        </div>
      );
    }
    return this.props.children;
  }
}
```

**修改 TimelineModal 组件：**
```typescript
// 增加缩略图加载失败的降级显示
{thumbnailUrl ? (
  <img
    src={thumbnailUrl}
    onError={(e) => {
      e.target.src = '/placeholders/scene-thumbnail.jpg';
    }}
    alt={`场景 ${index}`}
  />
) : (
  <div className="thumbnail-placeholder">
    <span>场景 {index + 1}</span>
  </div>
)}
```

---

### 修复 3：Modal 关闭功能 [P2]

**确保正确的 z-index：**
```css
/* TimelineModal.module.css */
.modalOverlay {
  z-index: 9999; /* 确保在最上层 */
}

.modalContent {
  z-index: 10000;
}
```

**添加点击外部关闭：**
```typescript
const handleOverlayClick = (e: React.MouseEvent) => {
  if (e.target === e.currentTarget) {
    onClose();
  }
};

<div className="modalOverlay" onClick={handleOverlayClick}>
```

---

## 测试建议

### 回归测试清单
- [ ] 上传新视频并验证所有 57 个缩略图生成成功
- [ ] 打开 Timeline Modal 验证所有缩略图正确显示
- [ ] 测试 Modal 关闭功能（按钮、ESC、点击外部）
- [ ] 测试 Toast 通知在 Modal 打开时仍能正确显示
- [ ] 测试音频提示功能

### 性能测试
- [ ] 测试 50+ 场景视频的处理时间
- [ ] 测试缩略图生成是否可以并行优化
- [ ] 测试 Modal 渲染大量场景的性能

---

## 总结

**关键发现：**
1. **核心问题**是缩略图生成失败，导致 56/57 个场景无法显示预览
2. **根本原因**可能是 FFmpeg 超时或进程管理问题
3. **影响**：用户无法正常使用 Timeline 功能查看处理结果

**建议修复顺序：**
1. 🔴 P0: 修复缩略图生成问题（增加超时、错误处理）
2. 🔴 P0: 添加 Error Boundary 和降级显示
3. 🟡 P2: 修复 Modal 关闭功能

**预期效果：**
修复后，用户可以正常查看所有场景的缩略图，Timeline Modal 功能完整可用。
