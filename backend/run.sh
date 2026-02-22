#!/bin/bash
# SmartCut Backend 启动脚本

cd "$(dirname "$0")"

PYTHON_BIN="/Users/apple/Documents/Claude Code/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

# 创建数据目录
mkdir -p data/uploads
mkdir -p data/tasks

# 启动 FastAPI 服务器
"$PYTHON_BIN" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
