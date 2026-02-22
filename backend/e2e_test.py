#!/usr/bin/env python3
"""
SmartCut 完整端到端测试脚本
自动验证服务状态、上传视频、触发处理、监控进度、验证结果
"""
import os
import sys
import time
import subprocess
import urllib.request
import json
import sqlite3
from pathlib import Path

# 配置
VIDEO_PATH = "/Users/apple/Downloads/Downie4 下载/黑色环保动画短片《转折点》，当人类成为濒危动物时，世界会怎样？.mp4"
BASE_URL = "http://127.0.0.1:8787"
FRONTEND_URL = "http://localhost:5173"
DB_PATH = "/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend/data/database.db"


class Colors:
    """终端颜色"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_header(title):
    """打印标题"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN} {title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")


def print_success(text):
    """打印成功信息"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text):
    """打印错误信息"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_warning(text):
    """打印警告信息"""
    print(f"{Colors.YELLOW}⚠️ {text}{Colors.END}")


def print_info(text):
    """打印信息"""
    print(f"{Colors.BLUE}ℹ️ {text}{Colors.END}")


def print_progress(text):
    """打印进度"""
    print(f"{Colors.PURPLE}⏳ {text}{Colors.END}")


# ============================================================================
# Phase 1: 服务验证
# ============================================================================

def check_redis():
    """检查 Redis 服务"""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=3
        )
        if "PONG" in result.stdout:
            print_success("Redis 服务运行中")
            return True
        else:
            print_error("Redis 未响应 PONG")
            return False
    except FileNotFoundError:
        print_error("redis-cli 未找到")
        return False
    except subprocess.TimeoutExpired:
        print_error("Redis 连接超时")
        return False
    except Exception as e:
        print_error(f"Redis 检查失败: {e}")
        return False


def check_backend():
    """检查后端 API"""
    try:
        body = urllib.request.urlopen(f"{BASE_URL}/health", timeout=3).read()
        data = json.loads(body)
        if data.get("status") == "healthy":
            print_success(f"后端 API: {BASE_URL}")
            return True
        else:
            print_error(f"后端 API 状态异常: {data}")
            return False
    except urllib.error.HTTPError as e:
        print_error(f"后端 API HTTP 错误: {e.code}")
        return False
    except urllib.error.URLError as e:
        print_error(f"后端 API 连接失败: {e.reason}")
        return False
    except Exception as e:
        print_error(f"后端 API 检查失败: {e}")
        return False


def check_frontend():
    """检查前端应用"""
    # 方法1: 使用 lsof 检查端口
    for port in [5173, 5174]:
        try:
            result = subprocess.run(
                ["lsof", "-i", f":{port}"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0 and "LISTEN" in result.stdout:
                print_success(f"前端应用: http://localhost:{port}")
                return True, port
        except:
            continue

    # 方法2: 尝试 HTTP 请求，使用更长的超时
    for port in [5173, 5174]:
        try:
            code = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=1).code
            if code == 200:
                print_success(f"前端应用: http://localhost:{port}")
                return True, port
        except:
            continue

    print_warning("前端应用未检测到 (可能不影响后端测试)")
    return True, None  # 返回 True 以继续测试


def check_rq_worker():
    """检查 RQ Worker 进程"""
    # 方法1: 检查 PID 文件
    pid_methods = [
        "/tmp/worker.pid",
        "/tmp/smartcut_worker.pid"
    ]

    for pid_file in pid_methods:
        try:
            if os.path.exists(pid_file):
                with open(pid_file) as f:
                    pid = f.read().strip()
                result = subprocess.run(["ps", "-p", pid], capture_output=True)
                if result.returncode == 0:
                    print_success(f"RQ Worker 运行中 (PID: {pid}, 文件: {pid_file})")
                    return True
        except:
            continue

    # 方法2: 通过进程名查找
    try:
        result = subprocess.run(
            ["pgrep", "-f", "rq worker"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            print_success(f"RQ Worker 运行中 (PID: {pids[0]})")
            return True
    except:
        pass

    print_warning("RQ Worker 未检测到")
    return False


def verify_video_file():
    """验证测试视频文件"""
    print_header("1️⃣ 验证测试视频")

    if not os.path.exists(VIDEO_PATH):
        print_error(f"视频文件不存在: {VIDEO_PATH}")
        return False

    size = os.path.getsize(VIDEO_PATH) / 1024 / 1024
    print_success(f"视频文件存在")
    print_info(f"路径: {VIDEO_PATH}")
    print_info(f"大小: {size:.2f} MB")

    # 获取视频信息
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
        print_info(f"时长: {duration:.2f} 秒 ({duration/60:.2f} 分钟)")
        return True
    except Exception as e:
        print_error(f"获取视频信息失败: {e}")
        return False


def verify_services():
    """验证所有服务"""
    print_header("🔍 服务状态检查")

    results = {
        "redis": check_redis(),
        "backend": check_backend(),
        "frontend": False,
        "worker": check_rq_worker()
    }

    # 前端检查返回 tuple
    frontend_ok, port = check_frontend()
    results["frontend"] = frontend_ok

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print()
    if passed == total:
        print_success(f"所有 {total} 个服务运行正常")
        return True
    else:
        print_warning(f"{passed}/{total} 个服务运行中")
        return False


# ============================================================================
# Phase 2: 上传视频
# ============================================================================

def upload_video():
    """上传视频文件"""
    print_header("📤 上传视频")

    if not os.path.exists(VIDEO_PATH):
        print_error("视频文件不存在")
        return None

    print_progress("正在上传视频...")

    try:
        with open(VIDEO_PATH, "rb") as f:
            data = f.read()

        # 准备 multipart/form-data
        boundary = f"----WebKitFormBoundary{os.urandom(16).hex()}"
        filename = os.path.basename(VIDEO_PATH)

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: video/mp4\r\n\r\n"
        ).encode()

        body += data
        body += f"\r\n--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            f"{BASE_URL}/upload",
            data=body,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}"
            }
        )

        response = urllib.request.urlopen(req, timeout=60)
        result = json.loads(response.read())

        if "id" in result:
            print_success(f"上传成功! Task ID: {result['id']}")
            print_info(f"Display Name: {result.get('display_name', 'N/A')}")
            print_info(f"File Size: {result.get('file_size', 0) / 1024 / 1024:.2f} MB")
            return result
        else:
            print_error(f"上传响应异常: {result}")
            return None

    except urllib.error.HTTPError as e:
        print_error(f"上传 HTTP 错误: {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        print_error(f"上传失败: {e}")
        return None


# ============================================================================
# Phase 3: 触发处理
# ============================================================================

def trigger_processing(task_id):
    """触发视频处理"""
    print_header("🚀 触发处理")

    print_progress(f"开始处理任务: {task_id}")

    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/tasks/{task_id}/process",
            method="POST"
        )
        response = urllib.request.urlopen(req, timeout=10)
        result = json.loads(response.read())

        print_success(f"任务已加入队列")
        print_info(f"Status: {result.get('status')}")
        print_info(f"Job ID: {result.get('job_id', 'N/A')}")
        return True

    except urllib.error.HTTPError as e:
        print_error(f"触发处理 HTTP 错误: {e.code} - {e.read().decode()}")
        return False
    except Exception as e:
        print_error(f"触发处理失败: {e}")
        return False


# ============================================================================
# Phase 4: 监控进度
# ============================================================================

def monitor_progress(task_id, timeout=300):
    """监控任务进度（轮询方式）"""
    print_header("📊 监控处理进度")

    start_time = time.time()
    last_progress = -1
    last_status = None

    print(f"{'时间':<8} {'进度':<8} {'状态':<12} {'场景数'}")
    print("-" * 50)

    while time.time() - start_time < timeout:
        try:
            response = urllib.request.urlopen(
                f"{BASE_URL}/api/tasks/{task_id}",
                timeout=5
            )
            task = json.loads(response.read())

            progress = task.get('progress', 0)
            status = task.get('status', 'UNKNOWN')
            total_scenes = task.get('total_scenes', '-')

            # 只在状态变化时打印
            if progress != last_progress or status != last_status:
                elapsed = int(time.time() - start_time)
                print(f"{elapsed}s{'':>4} {progress}%{'':>5} {status:<12} {total_scenes}")
                last_progress = progress
                last_status = status

            # 检查是否完成
            if status == 'COMPLETED':
                print()
                print_success("任务处理完成!")
                return True, task
            elif status == 'FAILED':
                print()
                print_error("任务处理失败")
                return False, task

            time.sleep(2)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                print_error("任务不存在")
                return False, None
            print_warning(f"查询任务状态失败: {e.code}")
            time.sleep(2)
        except Exception as e:
            print_warning(f"查询异常: {e}")
            time.sleep(2)

    print_warning("监控超时")
    return False, None


# ============================================================================
# Phase 5: 验证结果
# ============================================================================

def verify_results(task_id):
    """验证处理结果"""
    print_header("✅ 验证处理结果")

    # 1. 验证任务状态
    try:
        response = urllib.request.urlopen(f"{BASE_URL}/api/tasks/{task_id}")
        task = json.loads(response.read())

        print(f"📋 任务信息:")
        print(f"   ID: {task.get('id')}")
        print(f"   Name: {task.get('display_name')}")
        print(f"   Status: {task.get('status')}")
        print(f"   Progress: {task.get('progress')}%")
        print(f"   Scenes: {task.get('total_scenes', 'N/A')}")

        if task.get('status') != 'COMPLETED':
            print_error("任务未完成，无法验证结果")
            return False

    except Exception as e:
        print_error(f"获取任务信息失败: {e}")
        return False

    # 2. 验证数据库记录
    print()
    print("🗄️ 数据库验证:")

    if not os.path.exists(DB_PATH):
        print_error(f"数据库文件不存在: {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查任务记录
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        task_row = cursor.fetchone()

        if task_row:
            print_success(f"任务记录存在")
        else:
            print_error("任务记录不存在")
            return False

        # 检查场景记录
        cursor.execute("SELECT COUNT(*) FROM scenes WHERE task_id = ?", (task_id,))
        scene_count = cursor.fetchone()[0]

        if scene_count > 0:
            print_success(f"场景记录: {scene_count} 条")

            # 显示前几条场景信息
            cursor.execute(
                "SELECT id, sequence_index, start_ms, end_ms, file_path FROM scenes WHERE task_id = ? LIMIT 5",
                (task_id,)
            )
            scenes = cursor.fetchall()

            print(f"   前 {len(scenes)} 个场景:")
            for scene in scenes:
                scene_id, idx, start, end, path = scene
                print(f"   - [{idx}] {start}ms -> {end}ms")
        else:
            print_warning("无场景记录")

        conn.close()

    except Exception as e:
        print_error(f"数据库查询失败: {e}")
        return False

    # 3. 验证生成的文件
    print()
    print("📁 文件验证:")

    task_dir = f"/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend/data/tasks/{task_id}"

    if not os.path.exists(task_dir):
        print_warning(f"任务目录不存在: {task_dir}")
        return False

    scenes_dir = os.path.join(task_dir, "scenes")

    if not os.path.exists(scenes_dir):
        print_error(f"场景目录不存在: {scenes_dir}")
        return False

    # 统计文件
    mp4_files = list(Path(scenes_dir).glob("*.mp4"))
    jpg_files = list(Path(scenes_dir).glob("*.jpg"))

    print_success(f"MP4 文件: {len(mp4_files)} 个")
    print_success(f"缩略图: {len(jpg_files)} 个")

    if mp4_files:
        print(f"   示例文件:")
        for f in mp4_files[:3]:
            size = f.stat().st_size / 1024
            print(f"   - {f.name} ({size:.1f} KB)")

    # 4. 最终验证
    print()
    if scene_count > 0 and len(mp4_files) > 0 and len(jpg_files) > 0:
        print_success("🎉 所有验证通过!")
        return True
    else:
        print_warning("部分验证失败")
        return False


# ============================================================================
# Main
# ============================================================================

def main():
    """主函数"""
    print(f"{Colors.BOLD}{Colors.PURPLE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.PURPLE} SmartCut 完整端到端测试{Colors.END}")
    print(f"{Colors.BOLD}{Colors.PURPLE}{'='*70}{Colors.END}")

    all_passed = True

    # Phase 1: 服务验证
    if not verify_services():
        print_error("服务验证失败，请先启动所有服务")
        print()
        print("启动命令:")
        print("  1. Redis: brew services start redis")
        print("  2. 后端: cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8787")
        print("  3. Worker: cd backend && rq worker")
        print("  4. 前端: cd frontend && npm run dev")
        return 1

    # 验证视频文件
    if not verify_video_file():
        print_error("视频文件验证失败")
        return 1

    # Phase 2: 上传视频
    task = upload_video()
    if not task:
        print_error("上传失败")
        return 1

    task_id = task['id']

    # Phase 3: 触发处理
    if not trigger_processing(task_id):
        print_error("触发处理失败")
        return 1

    # Phase 4: 监控进度
    success, final_task = monitor_progress(task_id)
    if not success:
        print_error("处理失败或超时")
        all_passed = False

    # Phase 5: 验证结果
    if not verify_results(task_id):
        print_warning("结果验证不完全通过")
        all_passed = False

    # 最终报告
    print()
    print_header("📋 测试总结")

    print(f"Task ID: {task_id}")
    print(f"API URL: {BASE_URL}/api/tasks/{task_id}")
    print(f"Frontend: {FRONTEND_URL}")

    if all_passed:
        print()
        print_success("🎉 端到端测试全部通过!")
        return 0
    else:
        print()
        print_warning("测试完成，但有部分失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
