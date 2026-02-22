#!/usr/bin/env python3
"""测试后端 API 是否正常运行"""
import subprocess
import time
import urllib.error
import urllib.request
import sys


def fetch(url: str) -> tuple[int | None, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.getcode(), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="ignore")
    except Exception as exc:
        return None, str(exc)


def main() -> int:
    base_url = "http://127.0.0.1:8787"
    tests = [
        ("根路径", f"{base_url}/"),
        ("健康检查", f"{base_url}/health"),
        ("任务列表", f"{base_url}/api/tasks"),
    ]

    print("🚀 启动 FastAPI 服务器...")
    uvicorn_process = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8787"],
        cwd="/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    # 等待服务器启动
    time.sleep(3)

    results: list[tuple[str, str, int | str | None]] = []
    try:
        for name, url in tests:
            code, body = fetch(url)
            status = "✅" if code == 200 else "❌"
            results.append((name, status, code if code is not None else body))
            print(f"{status} {name}: {code if code is not None else body}")
    finally:
        uvicorn_process.terminate()
        uvicorn_process.wait(timeout=10)

    print("\n📊 测试总结:")
    all_passed = all(status == "✅" for _, status, _ in results)
    for name, status, _ in results:
        print(f"  {status} {name}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
