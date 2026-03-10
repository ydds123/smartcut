# SmartCut 智能拉片工具

> 飞书级丝滑的智能视频切分工具

## 项目概述

SmartCut 是一个智能视频切分工具，自动识别视频场景切换点，帮助视频剪辑师和内容运营快速筛选和预览视频片段。

## 核心功能

- **智能切分**：基于 PySceneDetect 自动识别场景切换点
- **实时进度**：SSE 实时推送处理进度
- **结果可视化**：时间轴弹窗、片段预览、关键帧缩略图
- **批量下载**：ZIP 打包所有切分片段

## 技术栈

### 前端
- React 19 + Vite + TypeScript
- Tailwind CSS + Shadcn/ui
- Zustand（UI State）+ React Query（Server State）

### 后端
- FastAPI（异步 Web 框架）
- RQ（任务队列，MVP）→ Celery（扩展）
- Redis（缓存/消息队列）
- SQLite（MVP）→ PostgreSQL（扩展）
- PySceneDetect + FFmpeg（视频处理）

### 实时通信
- SSE（Server-Sent Events，MVP）
- WebSocket（按需升级）

## 项目结构

```
smartcut/
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── components/      # UI 组件
│   │   ├── hooks/           # 自定义 Hooks
│   │   ├── stores/          # Zustand stores
│   │   ├── services/        # API 调用
│   │   ├── types/           # TypeScript 类型定义
│   │   └── utils/           # 工具函数
│   └── package.json
│
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/             # API 路由
│   │   ├── models/          # SQLAlchemy Models
│   │   ├── services/        # 业务逻辑
│   │   ├── workers/         # RQ Workers
│   │   └── core/            # 核心配置
│   └── requirements.txt
│
└── data/                     # 数据目录
    ├── uploads/             # 原始上传
    ├── tasks/               # 任务文件
    │   └── {TaskID}/
    │       ├── original.mp4
    │       └── scenes/
    │           ├── 001_000000_000015.mp4
    │           └── 001_thumb.jpg
    └── database.db          # SQLite
```

## 开发路线图

### 阶段 0：Idea → Planning ✅
- [x] PRD 文档撰写
- [x] 技术选型辩论（Council）
- [x] 创新方案探索（BeCreative）
- [x] 架构设计
- [x] 规划文档同步修复

### 阶段 1：MVP 开发（4-6 周）
- [ ] Sprint 1.1 - 前端基础（2 周）
- [ ] Sprint 1.2 - 后端基础（2 周）
- [ ] Sprint 1.3 - 核心功能（2 周）

### 阶段 2：产品化（3-4 周）
- [ ] Sprint 2.1 - 结果可视化
- [ ] Sprint 2.2 - 用户体验优化
- [ ] Sprint 2.3 - 对比拉片功能
- [ ] Sprint 2.4 - 部署优化

### 阶段 3：扩展与优化（持续）
- [ ] 切分模板市场
- [ ] 时间轴演奏体验
- [ ] AI 语义镜头识别

## 快速开始

### 一键启动（跨平台推荐）

#### macOS
```bash
cd smartcut
./tools/devstack.sh doctor
./tools/devstack.sh up
```

#### Windows (PowerShell)
```bash
cd smartcut
powershell -ExecutionPolicy Bypass -File .\tools\devstack.ps1 doctor
powershell -ExecutionPolicy Bypass -File .\tools\devstack.ps1 up
```

#### 通用（Python 直接调用）
```bash
python tools/devstack.py doctor
python tools/devstack.py up
```

常用运维命令：
```bash
python tools/devstack.py status
python tools/devstack.py ps
python tools/devstack.py logs backend --tail 120
python tools/devstack.py restart backend
python tools/devstack.py restart
python tools/devstack.py down
```

### 手动分服务启动（兼容旧方式）

前端：
```bash
cd frontend
npm install
npm run dev -- --host localhost --port 5173
```

后端：
```bash
cd backend
# 基础模式依赖（PySceneDetect + FastAPI）
pip install -r requirements.txt
# 可选：precision 模式（TransNetV2 融合）
# pip install -r requirements-precision.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Worker：
```bash
cd backend
python -m app.workers.worker
```

## 环境变量

```bash
# Backend
DATABASE_URL=sqlite:///./data/database.db
REDIS_URL=redis://localhost:6379/0
UPLOAD_DIR=./data/uploads
TASK_DIR=./data/tasks
MAX_UPLOAD_SIZE=524288000  # 500MB
FFMPEG_PROCESS_TIMEOUT_SEC=600
FFPROBE_TIMEOUT_SEC=30

# 可选：API token 认证（默认关闭）
API_AUTH_ENABLED=false
API_AUTH_TOKEN=

# 可选：/data 资源是否公开（默认公开）
DATA_PUBLIC_ACCESS=true

# 可选：轻量限流（默认关闭，单进程内存计数）
RATE_LIMIT_ENABLED=false
RATE_LIMIT_WINDOW_SEC=60
RATE_LIMIT_MUTATION_MAX_REQUESTS=30
RATE_LIMIT_UPLOAD_MAX_REQUESTS=8

# Frontend
VITE_API_URL=http://127.0.0.1:8000
VITE_SSE_URL=http://127.0.0.1:8000
VITE_API_TOKEN=
```

### 认证与访问控制示例

```bash
# 开启后端认证 + 关闭 /data 公共访问
API_AUTH_ENABLED=true
API_AUTH_TOKEN=change_me
DATA_PUBLIC_ACCESS=false

# 前端配置同一 token（API + SSE）
VITE_API_TOKEN=change_me
```

## 核心决策

详见 [findings.md](./findings.md)：

1. **任务队列**：RQ (MVP) → Celery (扩展)
2. **数据库**：SQLite (MVP) → PostgreSQL (扩展)
3. **实时通信**：SSE (MVP) → WebSocket (按需)
4. **前端状态**：Zustand (UI) + React Query (服务端)
5. **视频处理**：三阶段演进（伪异步 → RQ + Redis → 分布式）

## 创新方案

详见 [findings.md](./findings.md)：

1. **对比拉片功能**（Phase 1）
2. **时间轴演奏体验**（Phase 2）
3. **切分模板市场**（Phase 2）
4. **AI 语义镜头识别**（Phase 3）
5. **智能合并（反向切分）**（Phase 3）
6. **云端协作工作台**（Phase 4）
7. **AI 脚本匹配**（Phase 4）

## 边缘案例处理

详见 [findings.md](./findings.md)：

- 上传阶段：E-UP-01 ~ E-UP-04（4 个案例）
- 处理阶段：E-PRO-01 ~ E-PRO-04（4 个案例）
- 系统资源：E-SYS-01 ~ E-SYS-05（5 个案例）
- 用户交互：E-UX-01 ~ E-UX-03（3 个案例）

## 文档

- [PRD 文档](./SmartCut%20(智能拉片工具).md)
- [Task Plan](./task_plan.md)
- [Findings & Decisions](./findings.md)
- [Progress Log](./progress.md)
- [完整规划文档](./ancient-stirring-island.md)

## 许可证

MIT

---

**最后更新**: 2026-02-18
**当前版本**: v0.1.0 (规划阶段)
