#!/usr/bin/env python3
"""
TransNetV2 模型下载脚本

支持从 GitHub 或国内镜像下载预训练模型
"""
import sys
import logging
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from app.services.transnet_detector import download_model

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="下载 TransNetV2 预训练模型")
    parser.add_argument(
        "-o", "--output-dir",
        type=Path,
        default=None,
        help="模型输出目录（默认: ~/.smartcut/models）"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="强制重新下载"
    )

    args = parser.parse_args()

    try:
        model_path = download_model(output_dir=args.output_dir, force=args.force)
        print(f"\n✅ 模型下载成功: {model_path}")
        print(f"\n使用方法:")
        print(f"  detector = TransNetV2Detector(model_path='{model_path}')")
        print(f"  boundaries = detector.detect_boundaries(video_path)")
        return 0

    except Exception as e:
        logger.error(f"模型下载失败: {e}")
        default_target = (args.output_dir or (Path.home() / ".smartcut" / "models")) / "transnetv2-pytorch-weights.pth"
        print(f"\n❌ 下载失败: {e}")
        print("\n手动准备模型步骤:")
        print("  1. 克隆官方仓库: https://github.com/soCzech/TransNetV2")
        print("  2. 按 inference-pytorch/README.md 使用 convert_weights.py 生成 transnetv2-pytorch-weights.pth")
        print(f"  3. 将该文件保存到: {default_target}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
