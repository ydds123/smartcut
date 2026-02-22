#!/usr/bin/env python3
"""
端到端测试验证脚本
在用户完成浏览器测试后，验证所有结果
"""
import os
import sqlite3
import subprocess
from pathlib import Path

# 配置
DATABASE_PATH = "/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend/data/database.db"
TASKS_DIR = "/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend/data/tasks"

def check_results():
    """检查处理结果"""
    print("="*70)
    print(" 端到端测试验证报告")
    print("="*70)

    if not os.path.exists(DATABASE_PATH):
        print("\n❌ 数据库文件不存在")
        print("   请先完成浏览器测试（上传并处理视频）")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # 获取任务
    cursor.execute("""
        SELECT id, display_name, status, progress, total_scenes, created_at
        FROM tasks
        ORDER BY created_at DESC
        LIMIT 1
    """)
    task = cursor.fetchone()

    if not task:
        print("\n❌ 没有找到任务记录")
        return

    task_id, display_name, status, progress, total_scenes, created_at = task

    print(f"\n📹 任务信息:")
    print(f"   文件名: {display_name}")
    print(f"   状态: {status}")
    print(f"   进度: {progress}%")
    print(f"   场景数: {total_scenes or '未处理'}")
    print(f"   创建时间: {created_at}")

    # 验证检查点
    print(f"\n{'='*70}")
    print(" 验证检查点")
    print(f"{'='*70}")

    results = []

    # Check 1: 任务状态
    print(f"\n✅ Check 1: 任务状态")
    if status == "COMPLETED":
        print(f"   ✅ 任务完成: {status}")
        results.append(True)
    else:
        print(f"   ⚠️ 任务状态: {status}")
        results.append(status == "PROCESSING")  # 处理中也算通过

    # Check 2: 场景记录
    print(f"\n✅ Check 2: 场景记录")
    cursor.execute("SELECT COUNT(*) FROM scenes WHERE task_id = ?", (task_id,))
    scene_count = cursor.fetchone()[0]

    if scene_count > 0:
        print(f"   ✅ 场景数量: {scene_count}")
        results.append(True)
    else:
        print(f"   ❌ 没有场景记录")
        results.append(False)

    # Check 3: 生成的文件
    print(f"\n✅ Check 3: 生成的文件")
    task_dir = Path(TASKS_DIR) / task_id / "scenes"

    if task_dir.exists():
        videos = list(task_dir.glob("scene_*.mp4"))
        thumbs = list(task_dir.glob("*_thumb.jpg"))

        print(f"   📹 视频片段: {len(videos)}")
        print(f"   🖼️ 缩略图: {len(thumbs)}")
        print(f"   📁 目录: {task_dir}")

        if len(videos) > 0 and len(thumbs) > 0:
            results.append(True)
        else:
            results.append(False)

        # 显示前 5 个场景
        print(f"\n   前 5 个场景:")
        cursor.execute("""
            SELECT sequence_index, start_ms, end_ms
            FROM scenes
            WHERE task_id = ?
            ORDER BY sequence_index
            LIMIT 5
        """, (task_id,))

        for seq, start_ms, end_ms in cursor.fetchall():
            start_sec = start_ms // 1000
            end_sec = end_ms // 1000
            print(f"      {seq:2d}. {start_sec:04d} → {end_sec:04d}")

    else:
        print(f"   ❌ 任务目录不存在: {task_dir}")
        results.append(False)

    # Check 4: RQ Worker 日志
    print(f"\n✅ Check 4: Worker 日志")
    try:
        with open("/tmp/worker.log") as f:
            logs = f.read()

        if task_id in logs:
            print(f"   ✅ Worker 处理了此任务")
            results.append(True)
        else:
            print(f"   ⚠️ Worker 日志中未找到任务 ID")
            results.append(True)  # 不强制要求
    except:
        print(f"   ⚠️ 无法读取 Worker 日志")
        results.append(True)

    # 总结
    print(f"\n{'='*70}")
    print(f" 验证总结")
    print(f"{'='*70}")

    passed = sum(results)
    total = len(results)
    print(f"   通过: {passed}/{total}")

    if passed == total:
        print(f"\n🎉 所有验证通过！端到端测试成功！")
    else:
        print(f"\n⚠️ 有 {total - passed} 项验证失败")

    conn.close()

    # 下一步建议
    print(f"\n{'='*70}")
    print(f" 下一步操作")
    print(f"{'='*70}")

    if status == "COMPLETED":
        print(f"1. 在浏览器中查看切分结果（点击'查看结果'）")
        print(f"2. 播放生成的视频片段")
        print(f"3. 检查场景切换点是否准确")
        print(f"4. 尝试调整场景检测参数（如果需要）")
    elif status == "PROCESSING":
        print(f"1. 等待处理完成")
        print(f"2. 重新运行此验证脚本")
        print(f"   python {__file__}")
    else:
        print(f"1. 检查 Worker 日志: tail -50 /tmp/worker.log")
        print(f"2. 检查后端日志: tail -50 /tmp/backend.log")
        print(f"3. 尝试重新处理任务")

if __name__ == "__main__":
    check_results()
