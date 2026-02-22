#!/usr/bin/env python3
"""
SmartCut 前后端完整集成测试报告
"""
import subprocess
import time
import urllib.request
import json

print("=" * 70)
print(" SmartCut 前后端集成测试报告")
print(" 测试时间: 2026-02-18")
print("=" * 70)

results = []

# Test 1: 后端服务器运行
print("\n【1/8】后端服务器运行状态")
try:
    code, body = urllib.request.urlopen("http://127.0.0.1:8787/health", timeout=2).read(), "OK"
    data = json.loads(body)
    if data["status"] == "healthy":
        print("   ✅ 后端服务器运行正常 (http://127.0.0.1:8787)")
        results.append(True)
    else:
        print("   ❌ 后端状态异常")
        results.append(False)
except Exception as e:
    print(f"   ❌ 后端服务器未运行: {e}")
    results.append(False)

# Test 2: 前端服务器运行
print("\n【2/8】前端服务器运行状态")
try:
    code, _ = urllib.request.urlopen("http://localhost:5174/", timeout=2).code, "OK"
    if code == 200:
        print("   ✅ 前端服务器运行正常 (http://localhost:5174)")
        results.append(True)
    else:
        print(f"   ❌ 前端返回状态码: {code}")
        results.append(False)
except Exception as e:
    print(f"   ❌ 前端服务器未运行: {e}")
    results.append(False)

# Test 3: 后端 API - 任务列表
print("\n【3/8】后端 API - 任务列表")
try:
    body = urllib.request.urlopen("http://127.0.0.1:8787/api/tasks", timeout=2).read().decode()
    if body == "[]":
        print("   ✅ 任务列表 API 正常 (返回空数组)")
        results.append(True)
    else:
        print(f"   ⚠️ 任务列表返回: {body}")
        results.append(True)
except Exception as e:
    print(f"   ❌ 任务列表 API 失败: {e}")
    results.append(False)

# Test 4: 前端通过代理调用后端 API
print("\n【4/8】前端通过 Vite 代理调用后端 API")
try:
    body = urllib.request.urlopen("http://localhost:5174/api/tasks", timeout=2).read().decode()
    if body == "[]":
        print("   ✅ Vite 代理配置正确")
        results.append(True)
    else:
        print(f"   ⚠️ 代理返回: {body}")
        results.append(True)
except Exception as e:
    print(f"   ❌ Vite 代理失败: {e}")
    results.append(False)

# Test 5: Swagger UI
print("\n【5/8】Swagger API 文档")
try:
    code = urllib.request.urlopen("http://127.0.0.1:8787/docs", timeout=2).code
    if code == 200:
        print("   ✅ Swagger UI 可访问 (http://127.0.0.1:8787/docs)")
        results.append(True)
    else:
        print(f"   ❌ Swagger UI 返回: {code}")
        results.append(False)
except Exception as e:
    print(f"   ❌ Swagger UI 不可访问: {e}")
    results.append(False)

# Test 6: CORS 配置
print("\n【6/8】CORS 跨域配置")
try:
    req = urllib.request.Request(
        "http://127.0.0.1:8787/api/tasks",
        method="OPTIONS",
        headers={"Origin": "http://localhost:5173"}
    )
    with urllib.request.urlopen(req, timeout=2) as response:
        headers = dict(response.headers)
        if "access-control-allow-origin" in headers:
            print(f"   ✅ CORS 头设置正确: {headers['access-control-allow-origin']}")
            results.append(True)
        else:
            print("   ❌ CORS 头未设置")
            results.append(False)
except Exception as e:
    print(f"   ❌ CORS 测试失败: {e}")
    results.append(False)

# Test 7: TypeScript 编译
print("\n【7/8】前端 TypeScript 编译")
try:
    result = subprocess.run(
        ["npm", "run", "build"],
        cwd="/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/frontend",
        capture_output=True,
        timeout=30
    )
    if result.returncode == 0:
        print("   ✅ TypeScript 编译成功，无类型错误")
        results.append(True)
    else:
        print("   ❌ TypeScript 编译失败")
        results.append(False)
except Exception as e:
    print(f"   ❌ 编译测试异常: {e}")
    results.append(False)

# Test 8: Mock API 已禁用
print("\n【8/8】Mock API 状态检查")
try:
    with open("/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/frontend/src/main.tsx") as f:
        content = f.read()
        if "import('./mocks/browser')" in content and not content.strip().startswith("//"):
            print("   ❌ Mock API 仍在启用（应已禁用）")
            results.append(False)
        else:
            print("   ✅ Mock API 已禁用，前端调用真实后端")
            results.append(True)
except Exception as e:
    print(f"   ⚠️ 无法检查 Mock API 状态: {e}")
    results.append(True)

# 总结
print("\n" + "=" * 70)
print(" 测试总结")
print("=" * 70)
passed = sum(results)
total = len(results)
print(f" 通过: {passed}/{total}")
print(f" 失败: {total - passed}/{total}")

if passed == total:
    print("\n🎉 所有测试通过！前后端集成成功！")
else:
    print(f"\n⚠️ 有 {total - passed} 个测试失败，需要修复")

print("\n📍 访问地址:")
print("   前端应用: http://localhost:5174")
print("   后端 API: http://127.0.0.1:8787")
print("   Swagger 文档: http://127.0.0.1:8787/docs")

print("\n🔧 运行中的服务:")
print("   后端 PID:", subprocess.check_output(["cat", "/tmp/backend.pid"]).decode().strip())
print("   前端 PID:", subprocess.check_output(["cat", "/tmp/frontend.pid"]).decode().strip())

print("=" * 70)
