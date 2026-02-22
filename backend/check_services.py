#!/usr/bin/env python3
"""
SmartCut 服务启动状态
"""
import subprocess
import urllib.request
import json

print("="*70)
print(" SmartCut 服务状态")
print("="*70)

services = []

# Redis
try:
    result = subprocess.run(
        ["redis-cli", "ping"],
        capture_output=True,
        text=True,
        timeout=2
    )
    if "PONG" in result.stdout:
        print("✅ Redis: 运行中")
        services.append(True)
    else:
        print("❌ Redis: 未响应")
        services.append(False)
except:
    print("❌ Redis: 未运行")
    services.append(False)

# 后端 API
try:
    body = urllib.request.urlopen("http://127.0.0.1:8787/health", timeout=2).read()
    data = json.loads(body)
    if data["status"] == "healthy":
        print("✅ 后端 API: http://127.0.0.1:8787")
        services.append(True)
    else:
        print(f"⚠️ 后端 API: {data}")
        services.append(False)
except Exception as e:
    print(f"❌ 后端 API: {e}")
    services.append(False)

# RQ Worker
try:
    with open("/tmp/worker.pid") as f:
        pid = f.read().strip()
    result = subprocess.run(["ps", "-p", pid], capture_output=True)
    if result.returncode == 0:
        print(f"✅ RQ Worker: PID {pid}")
        services.append(True)
    else:
        print("❌ RQ Worker: 未运行")
        services.append(False)
except:
    print("❌ RQ Worker: 未运行")
    services.append(False)

# 前端
try:
    code = urllib.request.urlopen("http://localhost:5173/", timeout=2).code
    if code == 200:
        print("✅ 前端应用: http://localhost:5173")
        services.append(True)
    else:
        print(f"⚠️ 前端应用: 状态码 {code}")
        services.append(False)
except Exception as e:
    print(f"❌ 前端应用: {e}")
    services.append(False)

print("\n" + "="*70)

passed = sum(services)
total = len(services)

if passed == total:
    print("🎉 所有服务已启动！可以开始测试了！")
    print("\n📍 访问地址:")
    print("   前端应用: http://localhost:5173")
    print("   后端 API: http://127.0.0.1:8787")
    print("   Swagger 文档: http://127.0.0.1:8787/docs")
    print("\n📹 测试视频:")
    print("   /Users/apple/Downloads/Downie4 下载/黑色环保动画短片《转折点》，当人类成为濒危动物时，世界会怎样？.mp4")
else:
    print(f"⚠️ 有 {total - passed} 个服务未启动")

print("="*70)
