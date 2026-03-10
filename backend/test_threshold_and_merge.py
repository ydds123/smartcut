"""
单元测试：ThresholdDetector + merge_gap_frames
无需视频文件，秒级运行。
"""
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# 确保 backend 目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).parent))

# mock 掉 app.core.config 和 app.services.quality_tuning，避免依赖环境
import types

_BACKEND_DIR = str(Path(__file__).parent)
_SERVICES_DIR = str(Path(__file__).parent / "app" / "services")

# 注入 mock 模块，必须在真实 import 之前
_config_mod = types.ModuleType("app.core.config")
_settings = MagicMock()
_settings.TASK_DIR = "/tmp/test_tasks"
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

from app.services.video_processor import VideoProcessor  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_processor(config: dict | None = None) -> VideoProcessor:
    """创建一个不依赖真实文件系统的 VideoProcessor 实例。"""
    with patch("app.services.video_processor.Path.mkdir"), \
         patch("pathlib.Path.write_text"), \
         patch.object(VideoProcessor, "_ensure_unique_task_dir", return_value=Path("/tmp/fake_task")), \
         patch.object(VideoProcessor, "_extract_original_upload_name", return_value="test.mp4"):
        vp = VideoProcessor.__new__(VideoProcessor)
        vp.task_id = "test-task"
        vp.video_path = "/fake/video.mp4"
        from app.services.quality_tuning import DEFAULT_QUALITY_CONFIG
        vp.processing_config = dict(DEFAULT_QUALITY_CONFIG)
        if config:
            vp.processing_config.update(config)
        vp.task_dir = Path("/tmp/fake_task")
        vp.scenes_dir = Path("/tmp/fake_task/scenes")
        vp._transnet_detector = None
        vp.last_detection_report = {}
        return vp


# ===========================================================================
# Part 1A: _merge_scenes_by_gap() 纯逻辑测试
# ===========================================================================

class TestMergeScenesByGap:

    def test_gap_below_threshold_merges(self):
        """间隔 < 阈值 → 合并"""
        scenes = [(0, 1000), (1050, 2000)]
        result = VideoProcessor._merge_scenes_by_gap(scenes, merge_gap_ms=100)
        assert result == [(0, 2000)]

    def test_gap_at_threshold_not_merged(self):
        """间隔 == 阈值 → 不合并（严格小于）"""
        scenes = [(0, 1000), (1100, 2000)]
        result = VideoProcessor._merge_scenes_by_gap(scenes, merge_gap_ms=100)
        assert result == [(0, 1000), (1100, 2000)]

    def test_gap_above_threshold_not_merged(self):
        """间隔 > 阈值 → 不合并"""
        scenes = [(0, 1000), (1200, 2000)]
        result = VideoProcessor._merge_scenes_by_gap(scenes, merge_gap_ms=100)
        assert result == [(0, 1000), (1200, 2000)]

    def test_gap_zero_disables_merge(self):
        """gap=0 → 不启用，原样返回"""
        scenes = [(0, 1000), (1010, 2000)]
        result = VideoProcessor._merge_scenes_by_gap(scenes, merge_gap_ms=0)
        assert result == [(0, 1000), (1010, 2000)]

    def test_single_scene_unchanged(self):
        """单镜头 → 不处理"""
        scenes = [(0, 5000)]
        result = VideoProcessor._merge_scenes_by_gap(scenes, merge_gap_ms=500)
        assert result == [(0, 5000)]

    def test_multiple_consecutive_merges(self):
        """多段连续合并"""
        scenes = [(0, 100), (150, 300), (350, 500)]
        result = VideoProcessor._merge_scenes_by_gap(scenes, merge_gap_ms=100)
        assert result == [(0, 500)]


# ===========================================================================
# Part 1B: _detect_with_pyscene() 命令构造测试（mock subprocess）
# ===========================================================================

class TestDetectWithPysceneCmd:

    def _run_and_capture_cmd(self, config: dict) -> list[str]:
        """运行 _detect_with_pyscene，捕获传给 subprocess.run 的命令。"""
        vp = _make_processor(config)
        captured = {}

        fake_result = MagicMock()
        fake_result.stdout = ""
        fake_result.returncode = 0

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return fake_result

        with patch("app.services.video_processor.subprocess.run", side_effect=fake_run), \
             patch.object(vp, "_parse_scene_list", return_value=[(0, 5000)]):
            vp._detect_with_pyscene()

        return captured["cmd"]

    def test_default_no_threshold_detector(self):
        """默认参数：cmd 中不含 detect-threshold"""
        cmd = self._run_and_capture_cmd({})
        assert "detect-threshold" not in cmd

    def test_threshold_detector_enabled_cmd_contains_detect_threshold(self):
        """启用后：cmd 含 detect-threshold"""
        cmd = self._run_and_capture_cmd({
            "use_threshold_detector": True,
            "threshold_detector_threshold": 12.0,
            "threshold_detector_fade_bias": 0.0,
        })
        assert "detect-threshold" in cmd

    def test_threshold_detector_params_correct(self):
        """启用后：--threshold 和 --fade-bias 参数值正确"""
        cmd = self._run_and_capture_cmd({
            "use_threshold_detector": True,
            "threshold_detector_threshold": 15.5,
            "threshold_detector_fade_bias": -0.5,
        })
        idx = cmd.index("detect-threshold")
        # 找到 --threshold 参数
        assert "--threshold" in cmd[idx:]
        t_idx = cmd.index("--threshold", idx)
        assert cmd[t_idx + 1] == "15.5"
        # 找到 --fade-bias 参数
        assert "--fade-bias" in cmd[idx:]
        fb_idx = cmd.index("--fade-bias", idx)
        assert cmd[fb_idx + 1] == "-0.5"

    def test_threshold_detector_before_list_scenes(self):
        """detect-threshold 出现在 list-scenes 之前"""
        cmd = self._run_and_capture_cmd({
            "use_threshold_detector": True,
        })
        assert cmd.index("detect-threshold") < cmd.index("list-scenes")


# ===========================================================================
# Part 1C: detect_scenes() 二次合并触发测试（mock）
# ===========================================================================

class TestDetectScenesGapMerge:

    def _run_detect_scenes(self, config: dict, pyscene_scenes: list) -> list:
        """运行 detect_scenes，mock 掉 _detect_with_pyscene 和 fps/duration。"""
        vp = _make_processor(config)

        with patch.object(vp, "_detect_with_pyscene", return_value=pyscene_scenes), \
             patch.object(vp, "_get_video_fps", return_value=config.get("_fps", 25.0)), \
             patch.object(vp, "_get_video_duration_ms", return_value=10000):
            return vp.detect_scenes()

    def test_merge_gap_frames_zero_no_merge(self):
        """merge_gap_frames=0 → 不触发合并，返回原始镜头数"""
        # 3 个镜头，间隔 50ms（< 200ms），但 merge_gap_frames=0
        scenes = [(0, 1000), (1050, 2000), (2050, 3000)]
        result = self._run_detect_scenes(
            {"merge_gap_frames": 0, "min_scene_duration_ms_floor": 0, "min_scene_len_frames": 1},
            scenes,
        )
        assert len(result) == 3

    def test_merge_gap_frames_triggers_merge(self):
        """merge_gap_frames=5 → 碎镜头被合并"""
        # fps=25，5帧 = 200ms；间隔 50ms < 200ms → 全部合并
        scenes = [(0, 1000), (1050, 2000), (2050, 3000)]
        result = self._run_detect_scenes(
            {
                "merge_gap_frames": 5,
                "_fps": 25.0,
                "min_scene_duration_ms_floor": 0,
                "min_scene_len_frames": 1,
            },
            scenes,
        )
        assert len(result) == 1
        assert result[0] == (0, 3000)


class TestDetectScenesProgressMilestones:

    def _run_detect_scenes_with_progress(
        self,
        config: dict,
        pyscene_scenes: list[tuple[int, int]],
        *,
        merge_stage_progresses: list[int] | None = None,
    ) -> list[int]:
        vp = _make_processor(config)
        progress_events: list[int] = []

        def fake_merge_with_transnet(_scenes, progress_callback=None):
            if progress_callback:
                for value in merge_stage_progresses or []:
                    progress_callback(value)
            return pyscene_scenes, {"fusion_mode": "pyscene+transnet"}

        with patch.object(vp, "_detect_with_pyscene", return_value=pyscene_scenes), \
             patch.object(vp, "_read_stats_summary", return_value={}), \
             patch.object(vp, "_get_video_fps", return_value=config.get("_fps", 25.0)), \
             patch.object(vp, "_get_video_duration_ms", return_value=10000), \
             patch.object(vp, "_resolve_min_scene_duration_ms", return_value=0), \
             patch.object(vp, "_merge_short_scenes_by_duration", side_effect=lambda scenes, _: scenes), \
             patch.object(vp, "_merge_scenes_by_gap", side_effect=lambda scenes, _: scenes), \
             patch.object(vp, "_merge_with_transnet", side_effect=fake_merge_with_transnet):
            vp.detect_scenes(progress_callback=progress_events.append)

        return progress_events

    def test_precision_transnet_progress_hits_key_milestones(self):
        progress_events = self._run_detect_scenes_with_progress(
            {
                "detection_mode": "precision",
                "use_transnet": True,
                "merge_gap_frames": 0,
                "min_scene_duration_ms_floor": 0,
                "min_scene_len_frames": 1,
            },
            [(0, 1000), (1000, 2000)],
            merge_stage_progresses=[20, 52, 76, 100],
        )

        expected_milestones = [5, 20, 35, 45, 55, 60, 68, 74, 80, 95]
        for milestone in expected_milestones:
            assert milestone in progress_events
        assert progress_events == sorted(progress_events)
        assert progress_events[-1] == 95
        assert all(0 <= value <= 99 for value in progress_events)

    def test_fast_detection_progress_stays_simple_and_monotonic(self):
        progress_events = self._run_detect_scenes_with_progress(
            {
                "detection_mode": "fast",
                "use_transnet": False,
                "merge_gap_frames": 0,
                "min_scene_duration_ms_floor": 0,
                "min_scene_len_frames": 1,
            },
            [(0, 1000), (1000, 2000)],
        )

        assert progress_events == [5, 20, 35, 80, 95]
