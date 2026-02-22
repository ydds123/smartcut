from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import init_db
from app.api import upload, tasks, progress
import os

app = FastAPI(title="SmartCut API")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 启动时初始化数据库
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化数据库"""
    init_db()


# 路由注册
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(tasks.router, prefix="/api", tags=["tasks"])
app.include_router(progress.router, prefix="/api", tags=["progress"])

# 静态文件服务（用于访问缩略图和视频片段）
data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
if os.path.exists(data_dir):
    app.mount("/data", StaticFiles(directory=data_dir), name="data")


@app.get("/")
async def root():
    """根路径健康检查"""
    return {"message": "SmartCut API", "status": "running"}


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "healthy"}
