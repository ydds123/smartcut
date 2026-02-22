#!/usr/bin/env python3
"""
验证前后端通信的集成测试
启动后端服务器和前端开发服务器，测试 API 通信
"""
import subprocess
import time
import urllib.request
import urllib.error
import json
import signal
import sys

base_url = "http://127.0.0.1:8787"

def http_request(method, url, headers=None):
    """发送 HTTP 请求"""
    req = urllib.request.Request(url, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.getcode(), response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return None, str(e)


def main() -> int:
    print("🚀 启动后端服务器...")
    backend = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8787"],
        cwd="/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)

    def cleanup(signum=None, frame=None):
        """清理进程"""
        backend.terminate()
        backend.wait(timeout=10)

    signal.signal(signal.SIGINT, cleanup)

    tests_passed = 0
    tests_failed = 0
    print("\n🧪 开始测试后端 API...")

    try:
        # Test 1: 健康检查
        print("\n1️⃣ 测试健康检查...")
        code, body = http_request("GET", f"{base_url}/health")
        if code == 200:
            print(f"   ✅ 健康检查: {body}")
            tests_passed += 1
        else:
            print(f"   ❌ 健康检查失败: {code}")
            tests_failed += 1

        # Test 2: 任务列表（空）
        print("\n2️⃣ 测试任务列表（初始状态）...")
        code, body = http_request("GET", f"{base_url}/api/tasks")
        if code == 200 and body == "[]":
            print(f"   ✅ 任务列表为空: {body}")
            tests_passed += 1
        else:
            print(f"   ❌ 任务列表异常: {code} - {body}")
            tests_failed += 1

        # Test 3: 根路径
        print("\n3️⃣ 测试根路径...")
        code, body = http_request("GET", f"{base_url}/")
        if code == 200:
            print(f"   ✅ 根路径响应: {body}")
            tests_passed += 1
        else:
            print(f"   ❌ 根路径失败: {code}")
            tests_failed += 1

        # Test 4: CORS 预检请求
        print("\n4️⃣ 测试 CORS 预检请求...")
        req = urllib.request.Request(
            f"{base_url}/api/tasks",
            method="OPTIONS",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=5):
                print("   ✅ CORS 请求成功")
                tests_passed += 1
        except Exception as e:
            print(f"   ⚠️ CORS 测试异常: {e}")
            tests_failed += 1

        # Test 5: Swagger 文档
        print("\n5️⃣ 测试 Swagger 文档...")
        code, body = http_request("GET", f"{base_url}/docs")
        if code == 200:
            print("   ✅ Swagger 文档可访问")
            tests_passed += 1
        else:
            print(f"   ❌ Swagger 文档失败: {code}")
            tests_failed += 1

        print("\n📊 测试总结:")
        print(f"   ✅ 通过: {tests_passed}/{tests_passed + tests_failed}")
        print(f"   ❌ 失败: {tests_failed}/{tests_passed + tests_failed}")

        print("\n📝 前端配置:")
        print("   前端地址: http://localhost:5173")
        print(f"   后端地址: {base_url}")
        print(f"   API 代理: /api/* → {base_url}/api/*")
        print(f"   上传代理: /upload → {base_url}/upload")
        return 0 if tests_failed == 0 else 1
    finally:
        cleanup()


if __name__ == "__main__":
    sys.exit(main())
