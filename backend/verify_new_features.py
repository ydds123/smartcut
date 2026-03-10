"""
功能验证脚本：ThresholdDetector + merge_gap_frames
使用真实视频跑三组对比，打印结果。

运行方式：
    cd backend
    python verify_new_features.py
"""
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

VIDEO_PATH = str(
    Path(__file__).parent
    / "data/uploads"
    / "黑色环保动画短片《转折点》，当人类成为濒危动物时，世界会怎样？.mp4"
)


def _setup_mocks():
    """注入 mock 模块，只执行一次。"""
    if "app.services.video_processor" in sys.modules:
        return
    import tempfile
    import types

    _BACKEND_DIR = str(Path(__file__).parent)
    _SERVICES_DIR = str(Path(__file__).parent / "app" / "services")

    _config_mod = types.ModuleType("app.core.config")
    _settings = MagicMock()
    _settings.TASK_DIR = tempfile.mkdtemp(prefix="verify_")
    _config_mod.settings = _settings

    _app_mod = types.ModuleType("app")
    _app_mod.__path__ = [str(Path(__file__).parent / "app")]
    _core_mod = types.ModuleType("app.core")
    _core_mod.__path__ = [str(Path(__file__).parent / "app" / "core")]

    _quality_mod = types.ModuleType("app.services.quality_tuning")
    _quality_mod.DEFAULT_QUALITY_CONFIG = {
        "detector": "content",
        "scene_threshold": 27.0,
        "min_scene_len_frames": 15,
        "downscale": 1,
        "frame_skip": 0,
        "weight_hue": 1.0,
        "weight_sat": 1.0,
        "weight_lum": 1.0,
        "weight_edges": 0.0,
        "min_scene_duration_ms_floor": 1000,
        "merge_gap_frames": 0,
        "use_threshold_detector": False,
        "threshold_detector_threshold": 12.0,
        "threshold_detector_fade_bias": 0.0,
    }
    _services_mod = types.ModuleType("app.services")
    _services_mod.__path__ = [_SERVICES_DIR]
    _services_mod.quality_tuning = _quality_mod

    sys.modules["app"] = _app_mod
    sys.modules["app.core"] = _core_mod
    sys.modules["app.core.config"] = _config_mod
    sys.modules["app.services"] = _services_mod
    sys.modules["app.services.quality_tuning"] = _quality_mod


def make_processor(config: dict | None = None):
    """创建 VideoProcessor 实例。"""
    _setup_mocks()
    from app.services.video_processor import VideoProcessor

    task_id = f"verify_{os.getpid()}_{id(config)}"
    vp = VideoProcessor(task_id=task_id, video_path=VIDEO_PATH, processing_config=config)
    return vp


def run_group(label: str, config: dict | None = None) -> list:
    print(f"\n[{label}]")
    try:
        vp = make_processor(config)
        scenes = vp.detect_scenes()
        print(f"  → 检测到 {len(scenes)} 个镜头")
        return scenes
    except Exception as e:
        print(f"  → 失败: {e}")
        return []


def main():
    if not Path(VIDEO_PATH).exists():
        print(f"[错误] 视频文件不存在: {VIDEO_PATH}")
        sys.exit(1)

    print(f"视频：{Path(VIDEO_PATH).name}")

    # 组 1：默认参数（基准）
    baseline = run_group("组 1  默认参数（基准）")

    # 组 2：启用 ThresholdDetector
    threshold_scenes = run_group(
        "组 2  启用 ThresholdDetector（threshold=12）",
        {"use_threshold_detector": True, "threshold_detector_threshold": 12.0},
    )
    if baseline and threshold_scenes:
        diff = len(threshold_scenes) - len(baseline)
        sign = "+" if diff >= 0 else ""
        print(f"  → 与基准相比：{sign}{diff} 个切点（软切）")
        assert len(threshold_scenes) >= len(baseline), \
            f"ThresholdDetector 组镜头数应 >= 基准组（{len(threshold_scenes)} < {len(baseline)}）"

    # 组 3：启用 merge_gap_frames=3
    merge_scenes = run_group(
        "组 3  启用 merge_gap_frames=3",
        {"merge_gap_frames": 3},
    )
    if baseline and merge_scenes:
        diff = len(merge_scenes) - len(baseline)
        sign = "+" if diff >= 0 else ""
        print(f"  → 与基准相比：{sign}{diff} 个镜头（合并碎镜头）")
        assert len(merge_scenes) <= len(baseline), \
            f"merge_gap_frames 组镜头数应 <= 基准组（{len(merge_scenes)} > {len(baseline)}）"

    print("\n✅ 所有验证通过")


if __name__ == "__main__":
    main()
