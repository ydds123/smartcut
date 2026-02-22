#!/usr/bin/env python3
"""
端到端测试 - 使用真实视频
"""
import os
import sys
import time
import subprocess
import urllib.request
import json

# 测试视频路径
VIDEO_PATH = "/Users/apple/Downloads/Downie4 下载/黑色环保动画短片《转折点》，当人类成为濒危动物时，世界会怎样？.mp4"
BASE_URL = "http://127.0.0.1:8787"

def print_section(title):
    """打印分节标题"""
    print(f"\n{'='*70}")
    print(f" {title}")
    print(f"{'='*70}")

def check_video_file():
    """检查视频文件"""
    print_section("1️⃣ 验证测试视频")

    if not os.path.exists(VIDEO_PATH):
        print(f"   ❌ 视频文件不存在")
        return False

    size = os.path.getsize(VIDEO_PATH) / 1024 / 1024
    print(f"   ✅ 文件存在")
    print(f"   📁 路径: {VIDEO_PATH}")
    print(f"   📏 大小: {size:.2f} MB")

    # 获取视频时长
    try:
        result = subprocess.run(
            ["ffprobe",
             "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1",
             VIDEO_PATH],
            capture_output=True,
            text=True,
            check=True
        )
        duration = float(result.stdout.strip())
        print(f"   ⏱️ 时长: {duration:.2f} 秒 ({duration/60:.2f} 分钟)")
        return True
    except Exception as e:
        print(f"   ❌ 获取时长失败: {e}")
        return False

def check_services():
    """检查服务运行状态"""
    print_section("2️⃣ 检查服务状态")

    services = []

    # 后端 API
    try:
        body = urllib.request.urlopen(f"{BASE_URL}/health", timeout=2).read()
        data = json.loads(body)
        if data["status"] == "healthy":
            print("   ✅ 后端 API")
            services.append(True)
        else:
            print("   ⚠️ 后端 API 状态异常")
            services.append(False)
    except Exception as e:
        print(f"   ❌ 后端 API: {e}")
        services.append(False)

    # 前端
    try:
        code = urllib.request.urlopen("http://localhost:5174/", timeout=2).code
        if code == 200:
            print("   ✅ 前端应用")
            services.append(True)
        else:
            print(f"   ⚠️ 前端状态码: {code}")
            services.append(False)
    except Exception as e:
        print(f"   ❌ 前端: {e}")
        services.append(False)

    # Redis
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=2
        )
        if "PONG" in result.stdout:
            print("   ✅ Redis")
            services.append(True)
        else:
            print("   ❌ Redis")
            services.append(False)
    except Exception as e:
        print(f"   ❌ Redis: {e}")
        services.append(False)

    # RQ Worker
    try:
        with open("/tmp/worker.pid") as f:
            pid = f.read().strip()
        result = subprocess.run(["ps", "-p", pid], capture_output=True)
        if result.returncode == 0:
            print(f"   ✅ RQ Worker (PID: {pid})")
            services.append(True)
        else:
            print("   ❌ RQ Worker 未运行")
            services.append(False)
    except Exception as e:
        print(f"   ❌ RQ Worker: {e}")
        services.append(False)

    return all(services)

def print_instructions():
    """打印测试说明"""
    print_section("3️⃣ 浏览器测试说明")

    print("📍 测试步骤:")
    print()
    print("1. 打开浏览器访问: http://localhost:5174")
    print()
    print("2. 点击上传区域，选择文件:")
    print(f"   {VIDEO_PATH}")
    print()
    print("3. 上传完成后，点击'开始处理'按钮")
    print()
    print("4. 观察进度条实时更新（SSE 推送）")
    print()
    print("5. 等待处理完成（预计需要 1-2 分钟）")
    print()
    print("6. 点击'查看结果'查看切分片段")
    print()
    print("📊 预期结果:")
    print("   - 进度条从 0% 走到 100%")
    print("   - 状态变化: PENDING → QUEUED → PROCESSING → COMPLETED")
    print("   - 生成多个场景片段（每个场景一个 MP4 文件）")
    print("   - 每个片段有对应的缩略图")
    print()
    print("🔍 验证命令:")
    print("   查看任务列表:")
    print(f"     curl {BASE_URL}/api/tasks")
    print()
    print("   查看任务结果:")
    print(f"     curl {BASE_URL}/api/tasks/<task_id>/result")
    print()
    print("   查看生成的文件:")
    print(f"     ls -la ./data/tasks/<task_id>/scenes/")
    print()
    print("   查看数据库记录:")
    print(f"     sqlite3 ./data/database.db 'SELECT * FROM scenes;'")

def main():
    """主函数"""
    print("="*70)
    print(" SmartCut 端到端测试 - 真实视频")
    print("="*70)

    # 检查视频文件
    if not check_video_file():
        print("\n❌ 测试视频验证失败，退出")
        sys.exit(1)

    # 检查服务
    if not check_services():
        print("\n❌ 部分服务未运行，请先启动所有服务")
        sys.exit(1)

    # 打印测试说明
    print_instructions()

    print("\n" + "="*70)
    print(" ✅ 准备就绪！可以开始浏览器测试了")
    print("="*70)

if __name__ == "__main__":
    main()
