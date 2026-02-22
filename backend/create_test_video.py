#!/usr/bin/env python3
"""
创建测试视频脚本
使用 FFmpeg 生成一个包含多个场景的测试视频
"""
import subprocess
import os
from pathlib import Path

def create_test_video():
    """创建测试视频"""

    # 输出路径
    output_path = Path("/tmp/test_video.mp4")

    # 使用 FFmpeg 创建测试视频
    # 生成 30 秒视频，包含不同颜色背景模拟场景切换
    cmd = [
        "ffmpeg",
        "-f", "lavfi",
        "-i", "color=c=red:size=640x480:duration=5:r=30",  # 0-5秒: 红色
        "-f", "lavfi",
        "-i", "color=c=blue:size=640x480:duration=5:r=30",  # 5-10秒: 蓝色
        "-f", "lavfi",
        "-i", "color=c=green:size=640x480:duration=5:r=30",  # 10-15秒: 绿色
        "-f", "lavfi",
        "-i", "color=c=yellow:size=640x480:duration=5:r=30",  # 15-20秒: 黄色
        "-f", "lavfi",
        "-i", "color=c=purple:size=640x480:duration=5:r=30",  # 20-25秒: 紫色
        "-f", "lavfi",
        "-i", "color=c=orange:size=640x480:duration=5:r=30",  # 25-30秒: 橙色
        "-filter_complex", (
            "[0:v][1:v][2:v][3:v][4:v][5:v]"
            "concat=n=6:v=1:a=0[outv]"
        ),
        "-map", "[outv]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-y",
        str(output_path)
    ]

    print("🎬 创建测试视频...")
    print(f"   输出路径: {output_path}")
    print(f"   时长: 30 秒")
    print(f"   场景: 6 个（每 5 秒切换颜色）")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ 测试视频创建成功！")
        print(f"   文件大小: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
        return str(output_path)

    except subprocess.CalledProcessError as e:
        print(f"❌ 创建失败: {e.stderr}")
        return None

if __name__ == "__main__":
    video_path = create_test_video()

    if video_path:
        print(f"\n📍 测试视频路径: {video_path}")
        print("\n使用方法:")
        print("1. 在前端上传此视频")
        print("2. 点击'开始处理'")
        print("3. 观察进度条从 0% 走到 100%")
        print("4. 查看切分结果（应有 6 个场景）")
