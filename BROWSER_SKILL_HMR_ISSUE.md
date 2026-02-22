# Browser Skill 与 Vite HMR 兼容性问题

## 问题描述

Browser skill 使用 Playwright 的 `networkidle` 等待策略，在访问 Vite 开发服务器时持续超时。

## 根本原因

1. **Vite HMR 机制**：
   - Vite 通过 WebSocket 连接实现热模块替换
   - 连接在开发模式下持续活跃
   - 这是正常且必要的开发功能

2. **Playwright networkidle 策略**：
   - 要求 500ms 内网络连接数为 0
   - 适用于静态页面或生产环境
   - 与开发服务器的持续连接冲突

## 解决方案

### 方案 1: 使用 load 事件（推荐）

```typescript
await page.goto('http://localhost:5173', { waitUntil: 'load' });
```

**优点**：
- 等待 DOM 和资源加载完成
- 不要求网络空闲
- 适合 SPA 应用

### 方案 2: 使用 domcontentloaded 事件

```typescript
await page.goto('http://localhost:5173', { waitUntil: 'domcontentloaded' });
```

**优点**：
- 更快（不等待所有资源）
- 适合快速验证

### 方案 3: 自定义等待条件

```typescript
await page.goto('http://localhost:5173', { waitUntil: 'commit' });
await page.waitForSelector('input[type="file"]'); // 等待特定元素
```

**优点**：
- 灵活性高
- 可针对具体应用

### 方案 4: 生产模式测试

```bash
# 构建生产版本
bun run build

# 使用预览服务器
bun run preview

# 测试
bun run verify
```

**优点**：
- 接近真实环境
- 无 HMR 干扰

## 验证脚本

项目中提供了三个验证脚本：

1. **verify-quick.ts** - 快速验证（load 事件）
2. **verify-simple.ts** - 简化验证
3. **verify-full.ts** - 完整功能测试

使用方法：
```bash
bun verify-quick.ts
```

## 建议

- **开发环境测试**: 使用 `load` 或 `domcontentloaded`
- **CI/CD 测试**: 使用生产构建 + `networkidle`
- **功能测试**: 等待特定元素而非全局状态

## 相关文件

- `frontend/vite.config.ts` - Vite 配置
- `~/.claude/skills/Browser/Tools/Browse.ts` - Browser skill 实现
