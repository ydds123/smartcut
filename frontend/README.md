# SmartCut 前端项目

基于 React 19 + Vite 5 + TypeScript 5 构建的智能拉片工具前端应用。

## 技术栈

- **框架**: React 19.1 + Vite 6.2 + TypeScript 5.7
- **状态管理**:
  - Zustand (Client State)
  - React Query 5 (Server State)
- **样式**: Tailwind CSS 3.4
- **HTTP 客户端**: Axios 1.7
- **构建工具**: Vite 6.2

## 项目结构

```
src/
├── components/          # UI 组件
│   ├── upload/         # 上传相关
│   ├── task/           # 任务卡片/列表
│   ├── timeline/       # 时间轴 Modal
│   └── ui/             # 基础 UI 组件
├── stores/             # Zustand 状态管理
├── hooks/              # 自定义 React Hooks
├── services/           # API 服务层
├── types/              # TypeScript 类型定义
├── utils/              # 工具函数
└── lib/                # 第三方库配置
```

## 快速开始

### 安装依赖

```bash
npm install
```

### 开发模式

```bash
npm run dev
```

访问 http://localhost:5173

### 构建生产版本

```bash
npm run build
```

### 预览生产构建

```bash
npm run preview
```

## 环境变量

创建 `.env.local` 文件：

```bash
VITE_API_URL=http://127.0.0.1:8000
VITE_SSE_URL=http://127.0.0.1:8000
```

说明：本机开发优先使用 `127.0.0.1`，避免 `localhost` 在部分环境解析为 `::1` 导致连接拒绝。

## React 19 特性应用

- `useOptimistic` - 乐观更新（立即移除卡片）
- `useTransition` - 非紧急更新（任务列表过滤）
- 自定义 Hooks - SSE 进度实时推送

## 状态管理模式

- **Zustand** 管理 UI 状态（Modal 开关、Toast 队列）
- **React Query** 管理服务端状态（任务列表、进度查询）

## API 代理配置

Vite 开发服务器自动代理 `/api` 请求到后端（`http://127.0.0.1:8000`）。

## 当前 Sprint 状态

**Sprint 1.1 - 前端基础（进行中）**

✅ 项目初始化完成
✅ 组件库集成（Tailwind CSS）
✅ 核心目录结构创建
✅ TypeScript 类型定义
✅ Zustand + React Query 配置
✅ 上传组件实现
✅ 任务列表组件实现

🚧 下一步：后端基础开发（Sprint 1.2）
