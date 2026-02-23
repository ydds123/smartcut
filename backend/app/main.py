from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import progress, tasks, upload
from app.core.config import settings
from app.core.database import init_db
from app.core.security import require_api_token

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


# 路由注册（可开关 API token）
api_dependencies = [Depends(require_api_token)]
app.include_router(upload.router, prefix="/api", tags=["upload"], dependencies=api_dependencies)
app.include_router(tasks.router, prefix="/api", tags=["tasks"], dependencies=api_dependencies)
app.include_router(progress.router, prefix="/api", tags=["progress"], dependencies=api_dependencies)

# 静态文件服务（用于访问缩略图和视频片段）
data_dir = (Path(__file__).resolve().parents[1] / "data").resolve()
if data_dir.exists():
    if settings.DATA_PUBLIC_ACCESS:
        app.mount("/data", StaticFiles(directory=str(data_dir)), name="data")
    else:
        @app.get("/data/{file_path:path}", dependencies=[Depends(require_api_token)], tags=["data"])
        async def get_protected_data_file(file_path: str):
            candidate = (data_dir / file_path).resolve()
            if candidate == data_dir or data_dir not in candidate.parents:
                raise HTTPException(status_code=400, detail="Invalid data path")
            if not candidate.exists() or not candidate.is_file():
                raise HTTPException(status_code=404, detail="Data file not found")
            return FileResponse(candidate)


@app.get("/")
async def root():
    """根路径健康检查"""
    return {"message": "SmartCut API", "status": "running"}


@app.get("/health")
async def health():
    """健康检查端点"""
    return {"status": "healthy"}
