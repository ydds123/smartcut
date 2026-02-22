#!/usr/bin/env python3
"""
实时监控任务处理进度
"""
import time
import sqlite3
import os
from pathlib import Path

DATABASE_PATH = "/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend/data/database.db"

def get_latest_task():
    """获取最新的任务"""
    if not os.path.exists(DATABASE_PATH):
        return None

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, display_name, status, progress, total_scenes
        FROM tasks
        ORDER BY created_at DESC
        LIMIT 1
    """)

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            'id': row[0],
            'display_name': row[1],
            'status': row[2],
            'progress': row[3],
            'total_scenes': row[4]
        }
    return None

def get_task_scenes(task_id):
    """获取任务的场景列表"""
    if not os.path.exists(DATABASE_PATH):
        return []

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT sequence_index, start_ms, end_ms
        FROM scenes
        WHERE task_id = ?
        ORDER BY sequence_index
    """, (task_id,))

    rows = cursor.fetchall()
    conn.close()

    return rows

def format_time(ms):
    """格式化时间"""
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

def print_progress_bar(progress):
    """打印进度条"""
    bar_length = 40
    filled = int(bar_length * progress / 100)
    bar = '█' * filled + '░' * (bar_length - filled)
    return f"[{bar}] {progress}%"

def main():
    print("="*70)
    print(" SmartCut 任务监控")
    print("="*70)
    print("\n等待任务创建...\n")

    last_task_id = None

    while True:
        task = get_latest_task()

        if not task:
            print("   等待任务...", end="\r")
            time.sleep(1)
            continue

        # 新任务
        if task['id'] != last_task_id:
            print(f"\n📹 任务: {task['display_name']}")
            print(f"🆔 ID: {task['id']}")
            last_task_id = task['id']

        # 打印状态
        status_emoji = {
            'PENDING': '⏳',
            'QUEUED': '📥',
            'PROCESSING': '⚙️',
            'COMPLETED': '✅',
            'FAILED': '❌'
        }.get(task['status'], '❓')

        print(f"\r{status_emoji} 状态: {task['status']:<10} | 进度: {print_progress_bar(task['progress'])}", end="")

        # 完成或失败时显示详情
        if task['status'] in ['COMPLETED', 'FAILED']:
            print(f"\n\n最终状态: {task['status']}")
            print(f"总场景数: {task['total_scenes'] or 0}")

            if task['status'] == 'COMPLETED':
                scenes = get_task_scenes(task['id'])
                print(f"\n场景列表:")

                for i, (seq, start_ms, end_ms) in enumerate(scenes[:10], 1):
                    print(f"  {i:2d}. {format_time(start_ms)} → {format_time(end_ms)}")

                if len(scenes) > 10:
                    print(f"  ... 还有 {len(scenes) - 10} 个场景")

                # 检查生成的文件
                task_dir = Path(f"/Users/apple/Documents/Claude Code/01_项目/短片拉片工具/smartcut/backend/data/tasks/{task['id']}/scenes")
                if task_dir.exists():
                    videos = list(task_dir.glob("scene_*.mp4"))
                    thumbs = list(task_dir.glob("*_thumb.jpg"))
                    print(f"\n生成的文件:")
                    print(f"  📹 视频片段: {len(videos)} 个")
                    print(f"  🖼️ 缩略图: {len(thumbs)} 个")
                    print(f"  📁 目录: {task_dir}")

            print("\n" + "="*70)
            break

        time.sleep(0.5)

    print("\n监控结束")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n监控已停止")
