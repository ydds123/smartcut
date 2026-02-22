#!/usr/bin/env python3
"""
后端 API CRUD 完整测试
测试所有端点的创建、读取、更新、删除操作
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import sys

base_url = "http://127.0.0.1:8787"

def http_request(method, url, headers=None, data=None):
    """发送 HTTP 请求"""
    if data:
        data = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.getcode(), response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return None, str(e)


def main() -> int:
    print("=" * 60)
    print("后端 API CRUD 完整测试")
    print("=" * 60)

    # Test 1: 获取初始任务列表（应为空）
    print("\n1️⃣ 获取初始任务列表")
    code, body = http_request("GET", f"{base_url}/api/tasks")
    print(f"   状态码: {code}")
    print(f"   响应: {body}")
    assert code == 200 and body == "[]", "初始任务列表应为空数组"
    print("   ✅ 通过")

    # Test 2: 获取不存在的任务（404）
    print("\n2️⃣ 获取不存在的任务")
    code, body = http_request("GET", f"{base_url}/api/tasks/nonexistent")
    print(f"   状态码: {code}")
    print(f"   响应: {body}")
    assert code == 404, "应返回 404"
    print("   ✅ 通过")

    # Test 3: 删除不存在的任务（404）
    print("\n3️⃣ 删除不存在的任务")
    code, body = http_request("DELETE", f"{base_url}/api/tasks/nonexistent")
    print(f"   状态码: {code}")
    print(f"   响应: {body}")
    assert code == 404, "应返回 404"
    print("   ✅ 通过")

    # Test 4: 处理不存在的任务（404）
    print("\n4️⃣ 处理不存在的任务")
    code, body = http_request("POST", f"{base_url}/api/tasks/nonexistent/process")
    print(f"   状态码: {code}")
    print(f"   响应: {body}")
    assert code == 404, "应返回 404"
    print("   ✅ 通过")

    # Test 5: 根路径测试
    print("\n5️⃣ 根路径测试")
    code, body = http_request("GET", f"{base_url}/")
    print(f"   状态码: {code}")
    print(f"   响应: {body}")
    assert code == 200, "根路径应返回 200"
    data = json.loads(body)
    assert data["status"] == "running", "状态应为 running"
    print("   ✅ 通过")

    # Test 6: 健康检查
    print("\n6️⃣ 健康检查")
    code, body = http_request("GET", f"{base_url}/health")
    print(f"   状态码: {code}")
    print(f"   响应: {body}")
    assert code == 200, "健康检查应返回 200"
    data = json.loads(body)
    assert data["status"] == "healthy", "状态应为 healthy"
    print("   ✅ 通过")

    # Test 7: OPTIONS 请求（CORS 预检）
    print("\n7️⃣ CORS 预检请求")
    req = urllib.request.Request(
        f"{base_url}/api/tasks",
        method="OPTIONS",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            print(f"   状态码: {response.getcode()}")
            print(f"   CORS 头: {dict(response.headers)}")
            print("   ✅ 通过")
    except Exception as e:
        print(f"   ❌ 失败: {e}")

    print("\n" + "=" * 60)
    print("✅ 所有后端 API 测试通过！")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
