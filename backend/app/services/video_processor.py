"""
视频处理服务
集成 PySceneDetect 和 FFmpeg 进行场景检测和视频切分
"""
import subprocess
import os
import csv
from pathlib import Path
from typing import Any, List, Tuple, Optional, Callable, Dict
import logging
import time
import threading
import re

from app.core.config import settings
from app.core.telemetry import increment_counter, log_event
from app.services.quality_tuning import DEFAULT_QUALITY_CONFIG

logger = logging.getLogger(__name__)

# 延迟导入 TransNetV2（仅在需要时）
_transnet_detector = None


def _terminate_subprocess(process: subprocess.Popen, wait_timeout_sec: int = 5) -> None:
    """终止并回收子进程，避免遗留僵尸进程与 pipe 句柄泄漏。"""
    try:
        if process.poll() is None:
            process.kill()
    except Exception:
        logger.debug("failed to kill subprocess", exc_info=True)

    try:
        process.wait(timeout=wait_timeout_sec)
    except Exception:
        logger.debug("failed to wait subprocess termination", exc_info=True)

    for stream in (process.stdout, process.stderr):
        if stream is None:
            continue
        try:
            stream.close()
        except Exception:
            logger.debug("failed to close subprocess stream", exc_info=True)


class FFmpegProgressMonitor:
    """监控 FFmpeg 处理进度（基于开源最佳实践）"""

    def __init__(self, on_update: Callable[[Dict], None]):
        self.on_update = on_update
        self.duration: float = 0
        self._stop_event = threading.Event()

    def parse_progress_line(self, line: str) -> Optional[Tuple[str, str]]:
        """解析 FFmpeg progress 输出"""
        if '=' not in line:
            return None

        key, value = line.strip().split('=', 1)
        if key in ['out_time_ms', 'out_time', 'duration', 'frame', 'speed']:
            return key, value
        return None

    def calculate_progress(self, current_time: float) -> float:
        """计算进度百分比"""
        if self.duration <= 0:
            return 0
        return min(100, (current_time / self.duration) * 100)

    def monitor(self, process: subprocess.Popen):
        """在独立线程中监控 FFmpeg 进度"""
        try:
            for line in process.stderr:
                if self._stop_event.is_set():
                    break

                parsed = self.parse_progress_line(line)
                if parsed:
                    key, value = parsed
                    if key == 'out_time_ms':
                        try:
                            current_time = float(value) / 1000000  # 转换为秒
                            progress = self.calculate_progress(current_time)
                            self.on_update({
                                'current_time': current_time,
                                'progress': progress
                            })
                        except (ValueError, ZeroDivisionError):
                            pass
        except Exception as e:
            logger.debug(f"进度监控异常: {e}")

    def stop(self):
        """停止监控"""
        self._stop_event.set()


class VideoProcessor:
    """视频处理器"""

    def __init__(
        self,
        task_id: str,
        video_path: str,
        processing_config: Optional[dict[str, Any]] = None,
    ):
        self.task_id = task_id
        self.video_path = video_path
        self.processing_config: dict[str, Any] = dict(DEFAULT_QUALITY_CONFIG)
        if processing_config:
            self.processing_config.update(processing_config)
        task_root = Path(settings.TASK_DIR)
        task_root.mkdir(parents=True, exist_ok=True)

        original_name = self._extract_original_upload_name(task_id, video_path)
        safe_name = self._sanitize_task_dir_name(original_name)
        self.task_dir = self._ensure_unique_task_dir(task_root, safe_name)
        self.scenes_dir = self.task_dir / "scenes"
        self.scenes_dir.mkdir(parents=True, exist_ok=True)
        # 写入任务标记，便于后续按 task_id 精确清理目录
        (self.task_dir / ".task_id").write_text(self.task_id, encoding="utf-8")
        logger.info(f"Task {self.task_id}: 输出目录 {self.task_dir}")

        # TransNetV2 集成（延迟初始化）
        self._transnet_detector = None
        self.last_detection_report: dict[str, Any] = {}

    def set_processing_config(self, processing_config: dict[str, Any]):
        """更新当前任务处理配置。"""
        next_config = dict(DEFAULT_QUALITY_CONFIG)
        next_config.update(processing_config)
        self.processing_config = next_config
        self.last_detection_report = {}

    @staticmethod
    def _extract_original_upload_name(task_id: str, video_path: str) -> str:
        """从上传文件路径中还原原始文件名。"""
        file_name = Path(video_path).name
        prefix = f"{task_id}_"
        if file_name.startswith(prefix):
            original_name = file_name[len(prefix):]
            if original_name:
                return original_name
        return file_name or "untitled.mp4"

    @staticmethod
    def _sanitize_task_dir_name(file_name: str) -> str:
        """将目录名清洗为安全形式，同时保留中文和扩展名。"""
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", file_name).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)

        if cleaned in {"", ".", ".."}:
            return "untitled.mp4"
        return cleaned

    @staticmethod
    def _split_name_suffix(file_name: str) -> Tuple[str, str]:
        """
        按“主名 + 扩展名”拆分，支持多扩展（如 .tar.gz）。
        后缀插入格式：name_001.ext
        """
        suffix = "".join(Path(file_name).suffixes)
        if suffix and len(file_name) > len(suffix):
            stem = file_name[:-len(suffix)]
        else:
            stem = file_name
            suffix = ""

        stem = stem.rstrip(" .")
        if not stem:
            stem = "untitled"

        return stem, suffix

    @classmethod
    def _ensure_unique_task_dir(cls, task_root: Path, file_name: str) -> Path:
        """按 name, name_001, name_002... 方式创建唯一任务目录。"""
        stem, suffix = cls._split_name_suffix(file_name)
        counter = 0

        while True:
            if counter == 0:
                candidate_name = f"{stem}{suffix}"
            else:
                candidate_name = f"{stem}_{counter:03d}{suffix}"

            candidate = task_root / candidate_name
            try:
                candidate.mkdir(parents=True, exist_ok=False)
                return candidate
            except FileExistsError:
                counter += 1

    def detect_scenes_only(
        self,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> dict:
        """
        仅执行场景检测，不切分视频。用于预览确认流程。

        Returns:
            dict: {scenes: [(start_ms, end_ms)], duration_ms: int, report: dict}
        """
        scenes = self.detect_scenes(progress_callback=progress_callback)
        duration_ms = self._get_video_duration_ms()
        return {
            "scenes": scenes,
            "duration_ms": duration_ms,
            "report": dict(self.last_detection_report),
        }

    def split_video_from_scenes(
        self,
        scenes: List[Tuple[int, int]],
        progress_callback=None,
        output_indices: Optional[List[int]] = None,
    ) -> dict:
        """
        根据给定场景列表切分视频并生成缩略图。用于预览确认后的切分流程。

        Returns:
            dict: {output_files, thumbnails}
        """
        output_files = self.split_video(
            scenes,
            progress_callback=progress_callback,
            output_indices=output_indices,
        )
        thumbnails = self.generate_thumbnails_batch(
            output_files,
            scenes,
            progress_callback=progress_callback,
            output_indices=output_indices,
        )
        return {"output_files": output_files, "thumbnails": thumbnails}

    def detect_scenes(
        self,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> List[Tuple[int, int]]:
        """
        使用 PySceneDetect 检测场景切换点
        集成 TransNetV2 深度学习验证（如果启用）

        Returns:
            List of (start_ms, end_ms) tuples
        """
        logger.info(f"Task {self.task_id}: 开始场景检测")

        def emit_detection_progress(value: int) -> None:
            if progress_callback is None:
                return
            try:
                progress_callback(max(0, min(99, int(value))))
            except Exception as exc:  # pragma: no cover - 仅用于保护主流程
                logger.debug("Task %s: 检测进度回调失败 - %s", self.task_id, exc)

        # 检测模式：fast（仅 PySceneDetect）或 precision（PySceneDetect + TransNetV2）
        detection_mode = self.processing_config.get("detection_mode", "fast")
        use_transnet = bool(self.processing_config.get("use_transnet", False))
        start_time = time.perf_counter()
        emit_detection_progress(5)

        # Stage 1: PySceneDetect 获取候选场景
        pyscene_scenes = self._detect_with_pyscene()
        pyscene_boundaries = self._scenes_to_cut_frames(pyscene_scenes)

        # 读取 stats 帧级分数摘要（用于检测置信度报告）
        detector_type = self.processing_config.get("detector", "content")
        stats_threshold = (
            float(self.processing_config.get("adaptive_threshold", 3.0))
            if detector_type == "adaptive"
            else float(self.processing_config.get("scene_threshold", 27.0))
        )
        stats_summary = self._read_stats_summary(stats_threshold, detector_type=detector_type)
        emit_detection_progress(35)

        report: dict[str, Any] = {
            "fusion_mode": "pyscene_only",
            "detection_mode": detection_mode,
            "transnet_requested": bool(detection_mode == "precision" and use_transnet),
            "transnet_applied": False,
            "fallback_reason": None,
            "pyscene_scene_count": len(pyscene_scenes),
            "pyscene_boundary_count": len(pyscene_boundaries),
            "transnet_peak_count": 0,
            "retained_boundary_count": len(pyscene_boundaries),
            "added_boundary_count": 0,
            "final_scene_count": len(pyscene_scenes),
            "post_min_duration_merged_count": 0,
            "transnet_elapsed_sec": 0.0,
            "fusion_elapsed_sec": 0.0,
            **stats_summary,
        }

        # Stage 2: TransNetV2 验证（仅 precision 模式且启用时）
        if detection_mode == "precision" and use_transnet:
            emit_detection_progress(55)
            final_scenes, merge_report = self._merge_with_transnet(
                pyscene_scenes,
                progress_callback=lambda stage_progress: emit_detection_progress(
                    55 + int(max(0, min(100, stage_progress)) * 0.25)
                ),
            )
            report.update(merge_report)
            emit_detection_progress(80)
        else:
            final_scenes = pyscene_scenes
            logger.info(f"Task {self.task_id}: 使用快速模式（{detection_mode}），TransNetV2 已跳过")
            emit_detection_progress(80)

        fps = self._get_video_fps()
        min_scene_len_frames = int(self.processing_config.get("min_scene_len_frames", 15))
        min_scene_duration_ms_floor = int(self.processing_config.get("min_scene_duration_ms_floor", 1000))
        min_scene_duration_ms = self._resolve_min_scene_duration_ms(
            fps,
            min_scene_len_frames,
            min_scene_duration_ms_floor,
        )
        normalized_scenes = self._merge_short_scenes_by_duration(final_scenes, min_scene_duration_ms)
        report["post_min_duration_merged_count"] = max(0, len(final_scenes) - len(normalized_scenes))
        final_scenes = normalized_scenes

        # 二次合并：基于帧间隔（merge_gap_frames > 0 时启用）
        merge_gap_frames = int(self.processing_config.get("merge_gap_frames", 0))
        if merge_gap_frames > 0 and fps > 0:
            merge_gap_ms = int(round(merge_gap_frames / fps * 1000))
            gap_merged = self._merge_scenes_by_gap(final_scenes, merge_gap_ms)
            report["post_gap_merged_count"] = max(0, len(final_scenes) - len(gap_merged))
            final_scenes = gap_merged
        else:
            report["post_gap_merged_count"] = 0

        report["final_scene_count"] = len(final_scenes)
        report["fusion_elapsed_sec"] = round(time.perf_counter() - start_time, 3)
        self.last_detection_report = report
        emit_detection_progress(95)
        return final_scenes

    def _detect_with_pyscene(self) -> List[Tuple[int, int]]:
        """
        使用 PySceneDetect 进行场景检测（Stage 1）
        返回候选场景列表

        Returns:
            List of (start_ms, end_ms) tuples
        """
        detector = "adaptive" if self.processing_config.get("detector") == "adaptive" else "content"
        threshold = float(self.processing_config.get("scene_threshold", 27.0))
        min_scene_len_frames = int(self.processing_config.get("min_scene_len_frames", 15))
        downscale = int(self.processing_config.get("downscale", 0))
        frame_skip = int(self.processing_config.get("frame_skip", 0))
        weight_hue = float(self.processing_config.get("weight_hue", 1.0))
        weight_sat = float(self.processing_config.get("weight_sat", 1.0))
        weight_lum = float(self.processing_config.get("weight_lum", 1.0))
        weight_edges = float(self.processing_config.get("weight_edges", 0.0))

        stats_file = self.task_dir / "scenes.stats.csv"
        use_stats_file = frame_skip <= 0
        cmd = ["scenedetect", "-i", self.video_path]
        if use_stats_file:
            cmd.extend(["--stats", str(stats_file)])
            if stats_file.exists():
                logger.info(f"Task {self.task_id}: stats 文件已存在，PySceneDetect 将复用帧缓存")
        elif stats_file.exists():
            # Avoid accidentally reading stale stats generated from previous runs.
            try:
                stats_file.unlink(missing_ok=True)
            except OSError:
                logger.debug("Task %s: 清理旧 stats 文件失败（可忽略）", self.task_id)
            logger.info("Task %s: frame_skip > 0，已禁用 stats 文件输出", self.task_id)

        if downscale >= 1:
            cmd.extend(["--downscale", str(downscale)])
        if frame_skip > 0:
            cmd.extend(["--frame-skip", str(frame_skip)])

        if detector == "adaptive":
            adaptive_threshold = float(self.processing_config.get("adaptive_threshold", 3.0))
            adaptive_min_content_val = float(self.processing_config.get("adaptive_min_content_val", 15.0))
            adaptive_frame_window = int(self.processing_config.get("adaptive_frame_window", 2))
            cmd.extend(
                [
                    "detect-adaptive",
                    "--threshold",
                    str(adaptive_threshold),
                    "--min-content-val",
                    str(adaptive_min_content_val),
                    "--frame-window",
                    str(adaptive_frame_window),
                    "--min-scene-len",
                    str(min_scene_len_frames),
                ]
            )
        else:
            cmd.extend(
                [
                    "detect-content",
                    "--threshold",
                    str(threshold),
                    "--min-scene-len",
                    str(min_scene_len_frames),
                    "--weights",
                    str(weight_hue),
                    str(weight_sat),
                    str(weight_lum),
                    str(weight_edges),
                ]
            )

        use_threshold_detector = bool(self.processing_config.get("use_threshold_detector", False))
        if use_threshold_detector:
            threshold_detector_threshold = float(self.processing_config.get("threshold_detector_threshold", 12.0))
            threshold_detector_fade_bias = float(self.processing_config.get("threshold_detector_fade_bias", 0.0))
            cmd.extend([
                "detect-threshold",
                "--threshold", str(threshold_detector_threshold),
                "--fade-bias", str(threshold_detector_fade_bias),
            ])

        cmd.extend(["list-scenes", "-f", str(self.task_dir / "scenes.csv")])
        timeout_sec = int(self.processing_config.get("scenedetect_timeout_sec", 600))
        timeout_sec = max(30, min(timeout_sec, 3600))

        def _safe_stderr(exc: BaseException) -> str:
            if isinstance(exc, subprocess.CalledProcessError):
                return (exc.stderr or "").strip()
            if isinstance(exc, subprocess.TimeoutExpired):
                stderr = exc.stderr or ""
                if isinstance(stderr, bytes):
                    return stderr.decode(errors="ignore").strip()
                return str(stderr).strip()
            return str(exc)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout_sec,
            )
            logger.info(f"Task {self.task_id}: 场景检测完成")
            logger.debug(f"PySceneDetect output: {result.stdout}")

            # 解析 CSV 文件获取场景时间点
            return self._parse_scene_list()

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
            logger.warning(f"Task {self.task_id}: 场景检测失败，回退默认配置 - {_safe_stderr(e)}")
            fallback_cmd = [
                "scenedetect",
                "-i",
                self.video_path,
                "detect-content",
                "list-scenes",
                "-f",
                str(self.task_dir / "scenes.csv"),
            ]
            if use_stats_file:
                fallback_cmd[3:3] = ["--stats", str(stats_file)]
            try:
                subprocess.run(
                    fallback_cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=timeout_sec,
                )
                logger.info(f"Task {self.task_id}: 默认配置回退检测成功")
                return self._parse_scene_list()
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as fallback_exc:
                logger.error(
                    "Task %s: 回退检测也失败，降级为整片单场景 - %s",
                    self.task_id,
                    _safe_stderr(fallback_exc),
                )
                return [(0, self._get_video_duration_ms())]

    def _parse_scene_list(self) -> List[Tuple[int, int]]:
        """解析 PySceneDetect 生成的 CSV 文件"""
        scenes = []
        csv_path = self.task_dir / "scenes.csv"

        if not csv_path.exists():
            logger.warning(f"Task {self.task_id}: 场景列表文件不存在")
            return [(0, self._get_video_duration_ms())]

        with open(csv_path, 'r', newline='') as f:
            rows = list(csv.reader(f))

        # PySceneDetect CSV 格式:
        # 第1行: Timecode List: ...
        # 第2行: Scene Number,Start Frame,Start Timecode,...
        # 从第3行开始是数据
        if len(rows) < 3:
            logger.warning(f"Task {self.task_id}: 场景列表文件格式异常（行数不足）")
            return [(0, self._get_video_duration_ms())]

        header_parts = [col.strip() for col in rows[1]]
        try:
            start_col = header_parts.index("Start Timecode")
            end_col = header_parts.index("End Timecode")
        except ValueError:
            logger.warning(f"Task {self.task_id}: CSV 列名未找到，回退硬编码索引")
            start_col = 2
            end_col = 5

        for row_no, parts in enumerate(rows[2:], start=3):
            if not parts or not any(str(col).strip() for col in parts):
                continue
            if len(parts) > max(start_col, end_col):
                try:
                    start_ms = self._timecode_to_ms(parts[start_col].strip())
                    end_ms = self._timecode_to_ms(parts[end_col].strip())
                except ValueError as exc:
                    logger.warning("Task %s: 第 %s 行时间码无效，已跳过: %s", self.task_id, row_no, exc)
                    continue
                if end_ms <= start_ms:
                    logger.warning(
                        "Task %s: 第 %s 行时间区间非法（start=%s, end=%s），已跳过",
                        self.task_id,
                        row_no,
                        start_ms,
                        end_ms,
                    )
                    continue
                scenes.append((start_ms, end_ms))

        if not scenes:
            logger.warning(f"Task {self.task_id}: 未检测到场景")
            return [(0, self._get_video_duration_ms())]

        return scenes

    @staticmethod
    def _find_stats_score_column(header: list[str], candidates: tuple[str, ...]) -> tuple[Optional[int], Optional[str]]:
        for candidate in candidates:
            candidate_lower = candidate.lower()
            for idx, column_name in enumerate(header):
                normalized = column_name.strip().lower()
                if normalized == candidate_lower:
                    return idx, column_name.strip()
                if normalized.startswith(f"{candidate_lower} ") or normalized.startswith(f"{candidate_lower}("):
                    return idx, column_name.strip()
        return None, None

    def _read_stats_summary(self, threshold: float, detector_type: str = "content") -> dict[str, Any]:
        """读取 PySceneDetect stats CSV，返回帧级分数摘要（用于检测置信度报告）。"""
        stats_path = self.task_dir / "scenes.stats.csv"
        if not stats_path.exists():
            return {}

        try:
            with open(stats_path, 'r', newline='') as f:
                rows = list(csv.reader(f))

            if len(rows) < 2:
                return {}

            header = [col.strip() for col in rows[0]]
            if detector_type == "adaptive":
                candidates = ("adaptive_ratio", "content_val", "delta_lum", "delta_hue", "delta_sat")
            else:
                candidates = ("content_val", "delta_lum", "delta_hue", "delta_sat", "adaptive_ratio")
            score_col, score_column_name = self._find_stats_score_column(header, candidates)

            if score_col is None:
                return {}

            scores: list[float] = []
            for parts in rows[1:]:
                if len(parts) > score_col:
                    try:
                        scores.append(float(parts[score_col].strip()))
                    except ValueError:
                        pass

            if not scores:
                return {}

            near_miss_count = 0
            if threshold > 0:
                near_miss_count = sum(1 for s in scores if threshold * 0.8 <= s < threshold)
            return {
                "stats_score_column": score_column_name,
                "stats_score_max": round(max(scores), 3),
                "stats_score_mean": round(sum(scores) / len(scores), 3),
                "stats_near_miss_count": near_miss_count,
                "stats_frame_count": len(scores),
            }
        except Exception as exc:
            logger.debug(f"Task {self.task_id}: stats 摘要读取失败 - {exc}")
            return {}

    def _get_transnet_detector(self):
        """延迟初始化 TransNetV2 检测器"""
        if self._transnet_detector is None:
            try:
                from app.services.transnet_detector import TransNetV2Detector

                mode = self.processing_config.get("detection_mode", "precision")
                threshold = float(self.processing_config.get("transnet_threshold", 0.3))
                tolerance_frames = int(self.processing_config.get("transnet_tolerance_frames", 12))
                window_size = int(self.processing_config.get("transnet_window_size", 100))

                self._transnet_detector = TransNetV2Detector(
                    mode=mode,
                    threshold=threshold,
                    tolerance_frames=tolerance_frames,
                    window_size=window_size,
                )

                logger.info(f"Task {self.task_id}: TransNetV2 检测器初始化成功 ({mode})")

            except ImportError as e:
                logger.warning(f"Task {self.task_id}: TransNetV2 不可用 - {e}")
                self._transnet_detector = False  # 标记为不可用

        return self._transnet_detector if self._transnet_detector else None

    def _merge_with_transnet(
        self,
        pyscene_scenes: List[Tuple[int, int]],
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> Tuple[List[Tuple[int, int]], Dict[str, Any]]:
        """
        与 TransNetV2 结果融合（Stage 2）。
        融合策略：候选验证 + 高置信补边 + 最小间隔去抖。
        """
        def emit_merge_progress(value: int) -> None:
            if progress_callback is None:
                return
            try:
                progress_callback(max(0, min(100, int(value))))
            except Exception as exc:  # pragma: no cover - 仅用于保护主流程
                logger.debug("Task %s: TransNet 融合进度回调失败 - %s", self.task_id, exc)

        report: dict[str, Any] = {
            "fusion_mode": "pyscene+transnet",
            "transnet_applied": False,
            "fallback_reason": None,
            "transnet_peak_count": 0,
            "retained_boundary_count": 0,
            "added_boundary_count": 0,
            "transnet_elapsed_sec": 0.0,
        }
        emit_merge_progress(2)

        detector = self._get_transnet_detector()
        if detector is None:
            fallback_reason = "transnet_detector_unavailable"
            logger.warning(f"Task {self.task_id}: TransNetV2 不可用，返回 PySceneDetect 结果")
            report["fusion_mode"] = "pyscene_only"
            report["fallback_reason"] = fallback_reason
            report["retained_boundary_count"] = len(self._scenes_to_cut_frames(pyscene_scenes))
            emit_merge_progress(100)
            return pyscene_scenes, report

        if not detector.is_available():
            fallback_reason = "transnet_model_unavailable"
            logger.warning(f"Task {self.task_id}: TransNetV2 模型加载失败，返回 PySceneDetect 结果")
            report["fusion_mode"] = "pyscene_only"
            report["fallback_reason"] = fallback_reason
            report["retained_boundary_count"] = len(self._scenes_to_cut_frames(pyscene_scenes))
            emit_merge_progress(100)
            return pyscene_scenes, report

        try:
            emit_merge_progress(10)
            fps = self._get_video_fps()
            if fps <= 0:
                fallback_reason = "invalid_fps"
                logger.warning(f"Task {self.task_id}: FPS 无效，回退 PySceneDetect 结果")
                report["fusion_mode"] = "pyscene_only"
                report["fallback_reason"] = fallback_reason
                report["retained_boundary_count"] = len(self._scenes_to_cut_frames(pyscene_scenes))
                emit_merge_progress(100)
                return pyscene_scenes, report

            duration_ms = self._get_video_duration_ms()
            if duration_ms <= 0:
                fallback_reason = "invalid_duration"
                logger.warning(f"Task {self.task_id}: 视频时长无效，回退 PySceneDetect 结果")
                report["fusion_mode"] = "pyscene_only"
                report["fallback_reason"] = fallback_reason
                report["retained_boundary_count"] = len(self._scenes_to_cut_frames(pyscene_scenes))
                emit_merge_progress(100)
                return pyscene_scenes, report

            candidate_frames = self._scenes_to_cut_frames(pyscene_scenes, fps=fps)
            emit_merge_progress(18)
            transnet_start = time.perf_counter()
            transnet_boundaries = detector.detect_boundaries(self.video_path)
            report["transnet_elapsed_sec"] = round(time.perf_counter() - transnet_start, 3)
            report["transnet_peak_count"] = len(transnet_boundaries)
            emit_merge_progress(52)
            if not transnet_boundaries and candidate_frames:
                fallback_reason = "transnet_no_boundaries"
                logger.warning(f"Task {self.task_id}: TransNet 未输出边界，回退 PySceneDetect")
                report["fusion_mode"] = "pyscene_only"
                report["fallback_reason"] = fallback_reason
                report["retained_boundary_count"] = len(candidate_frames)
                emit_merge_progress(100)
                return pyscene_scenes, report

            tolerance_frames = int(self.processing_config.get("transnet_tolerance_frames", 12))
            additional_threshold = float(
                self.processing_config.get("transnet_additional_boundary_threshold", 0.55)
            )
            min_gap_frames = int(self.processing_config.get("transnet_only_min_gap_frames", 12))
            soft_candidate_multiplier = float(
                self.processing_config.get("transnet_soft_candidate_multiplier", 0.75)
            )
            soft_candidate_multiplier = max(0.5, min(1.0, soft_candidate_multiplier))
            soft_candidate_threshold = max(
                0.12,
                min(
                    additional_threshold - 0.05,
                    float(self.processing_config.get("transnet_threshold", 0.3)) * soft_candidate_multiplier,
                ),
            )
            soft_candidate_threshold = round(soft_candidate_threshold, 3)
            candidate_scores = detector.score_candidates(self.video_path, candidate_frames)
            report["soft_candidate_multiplier"] = round(soft_candidate_multiplier, 2)
            report["soft_candidate_threshold"] = soft_candidate_threshold
            emit_merge_progress(78)

            retained_frames: list[int] = []
            boundary_scores: dict[int, float] = {}
            soft_retained_count = 0
            for frame in candidate_frames:
                nearest_prob = self._nearest_boundary_prob(frame, transnet_boundaries, tolerance_frames)
                if nearest_prob is not None:
                    retained_frames.append(frame)
                    boundary_scores[frame] = max(nearest_prob, candidate_scores.get(frame, 0.0))
                    continue
                candidate_prob = candidate_scores.get(frame, 0.0)
                if candidate_prob >= soft_candidate_threshold:
                    retained_frames.append(frame)
                    boundary_scores[frame] = candidate_prob
                    soft_retained_count += 1

            added_frames: list[int] = []
            for frame, prob in sorted(transnet_boundaries.items(), key=lambda item: item[0]):
                if prob < additional_threshold:
                    continue
                if self._has_nearby_boundary(frame, retained_frames, min_gap_frames):
                    continue
                if self._has_nearby_boundary(frame, added_frames, min_gap_frames):
                    continue
                added_frames.append(frame)
                boundary_scores[frame] = prob

            merged_frames = sorted(set(retained_frames + added_frames))
            merged_frames = self._prune_close_boundaries(merged_frames, min_gap_frames)
            min_scene_len_frames = int(self.processing_config.get("min_scene_len_frames", 15))
            min_shot_gap_frames = max(min_gap_frames, min_scene_len_frames, int(round(fps)))
            merged_frames = self._enforce_min_shot_gap(
                merged_frames,
                boundary_scores,
                duration_ms,
                fps,
                min_shot_gap_frames,
            )
            report["min_shot_gap_frames"] = min_shot_gap_frames
            if candidate_frames and not merged_frames:
                fallback_reason = "transnet_filtered_all_boundaries"
                logger.warning(f"Task {self.task_id}: TransNet 过滤掉全部候选边界，回退 PySceneDetect")
                report["fusion_mode"] = "pyscene_only"
                report["fallback_reason"] = fallback_reason
                report["retained_boundary_count"] = len(candidate_frames)
                emit_merge_progress(100)
                return pyscene_scenes, report
            final_scenes = self._cut_frames_to_scenes(merged_frames, duration_ms, fps)

            if not final_scenes:
                fallback_reason = "empty_after_fusion"
                logger.warning(f"Task {self.task_id}: 融合结果为空，回退 PySceneDetect")
                report["fusion_mode"] = "pyscene_only"
                report["fallback_reason"] = fallback_reason
                report["retained_boundary_count"] = len(candidate_frames)
                emit_merge_progress(100)
                return pyscene_scenes, report

            report["transnet_applied"] = True
            report["retained_boundary_count"] = len(retained_frames)
            report["added_boundary_count"] = len(added_frames)
            report["soft_retained_boundary_count"] = soft_retained_count
            emit_merge_progress(100)
            logger.info(
                "Task %s: TransNetV2 融合完成，候选=%s 保留=%s 补边=%s 最终镜头=%s",
                self.task_id,
                len(candidate_frames),
                len(retained_frames),
                len(added_frames),
                len(final_scenes),
            )
            return final_scenes, report

        except Exception as e:
            logger.error(f"Task {self.task_id}: TransNetV2 验证失败 - {e}，回退 PySceneDetect 结果")
            report["fusion_mode"] = "pyscene_only"
            report["fallback_reason"] = f"transnet_exception:{e}"
            report["retained_boundary_count"] = len(self._scenes_to_cut_frames(pyscene_scenes))
            emit_merge_progress(100)
            return pyscene_scenes, report

    @staticmethod
    def _nearest_boundary_prob(
        target_frame: int,
        boundaries: dict[int, float],
        tolerance_frames: int,
    ) -> Optional[float]:
        nearest_prob: Optional[float] = None
        nearest_distance = tolerance_frames + 1
        for frame, prob in boundaries.items():
            distance = abs(frame - target_frame)
            if distance <= tolerance_frames and distance < nearest_distance:
                nearest_distance = distance
                nearest_prob = prob
        return nearest_prob

    @staticmethod
    def _has_nearby_boundary(target_frame: int, boundaries: list[int], max_distance: int) -> bool:
        for frame in boundaries:
            if abs(frame - target_frame) <= max_distance:
                return True
        return False

    @staticmethod
    def _prune_close_boundaries(boundaries: list[int], min_gap_frames: int) -> list[int]:
        if not boundaries:
            return []
        pruned = [boundaries[0]]
        for frame in boundaries[1:]:
            if frame - pruned[-1] >= min_gap_frames:
                pruned.append(frame)
        return pruned

    def _scenes_to_cut_frames(
        self,
        scenes: list[tuple[int, int]],
        fps: Optional[float] = None,
    ) -> list[int]:
        if len(scenes) <= 1:
            return []
        actual_fps = fps if fps and fps > 0 else self._get_video_fps()
        if actual_fps <= 0:
            return []
        cut_frames: list[int] = []
        for start_ms, _ in scenes[1:]:
            frame = int(round((start_ms / 1000.0) * actual_fps))
            if frame > 0:
                cut_frames.append(frame)
        return sorted(set(cut_frames))

    @staticmethod
    def _cut_frames_to_scenes(
        cut_frames: list[int],
        duration_ms: int,
        fps: float,
    ) -> list[tuple[int, int]]:
        if duration_ms <= 0 or fps <= 0:
            return []
        if not cut_frames:
            return [(0, duration_ms)]

        duration_frame = int(round((duration_ms / 1000.0) * fps))
        valid_frames = sorted(set(frame for frame in cut_frames if 0 < frame < duration_frame))
        if not valid_frames:
            return [(0, duration_ms)]

        scenes: list[tuple[int, int]] = []
        previous_ms = 0
        for frame in valid_frames:
            cut_ms = int(round((frame / fps) * 1000))
            if cut_ms <= previous_ms:
                continue
            scenes.append((previous_ms, cut_ms))
            previous_ms = cut_ms

        if previous_ms < duration_ms:
            scenes.append((previous_ms, duration_ms))

        return [segment for segment in scenes if segment[1] > segment[0]]

    @staticmethod
    def _resolve_min_scene_duration_ms(
        fps: float,
        min_scene_len_frames: int,
        min_scene_duration_ms_floor: int = 1000,
    ) -> int:
        """
        Resolve hard minimum scene duration.
        Lower bound can be configured per task to balance fast cuts vs. stability.
        """
        fps_safe = fps if fps > 0 else 25.0
        by_frames_ms = int(round((max(1, min_scene_len_frames) / fps_safe) * 1000))
        floor_ms = max(0, int(min_scene_duration_ms_floor))
        return max(floor_ms, by_frames_ms)

    @staticmethod
    def _merge_short_scenes_by_duration(
        scenes: list[tuple[int, int]],
        min_scene_duration_ms: int,
    ) -> list[tuple[int, int]]:
        if len(scenes) <= 1 or min_scene_duration_ms <= 0:
            return scenes

        merged = [(max(0, int(start_ms)), max(0, int(end_ms))) for start_ms, end_ms in scenes if end_ms > start_ms]
        if len(merged) <= 1:
            return merged

        changed = True
        while changed and len(merged) > 1:
            changed = False
            for idx, (start_ms, end_ms) in enumerate(list(merged)):
                duration_ms = end_ms - start_ms
                if duration_ms >= min_scene_duration_ms:
                    continue

                changed = True
                if idx == 0:
                    next_start, next_end = merged[idx + 1]
                    merged[idx + 1] = (start_ms, next_end)
                    del merged[idx]
                    break
                if idx == len(merged) - 1:
                    prev_start, _ = merged[idx - 1]
                    merged[idx - 1] = (prev_start, end_ms)
                    del merged[idx]
                    break

                prev_start, prev_end = merged[idx - 1]
                next_start, next_end = merged[idx + 1]
                prev_duration = prev_end - prev_start
                next_duration = next_end - next_start
                if prev_duration <= next_duration:
                    merged[idx - 1] = (prev_start, end_ms)
                    del merged[idx]
                else:
                    merged[idx + 1] = (start_ms, next_end)
                    del merged[idx]
                break

        return [segment for segment in merged if segment[1] > segment[0]]

    @staticmethod
    def _merge_scenes_by_gap(
        scenes: list[tuple[int, int]],
        merge_gap_ms: int,
    ) -> list[tuple[int, int]]:
        """合并边界间隔小于 merge_gap_ms 的相邻镜头（二次合并，解决碎镜头）"""
        if len(scenes) <= 1 or merge_gap_ms <= 0:
            return scenes

        merged = list(scenes)
        changed = True
        while changed and len(merged) > 1:
            changed = False
            for idx in range(len(merged) - 1):
                _, end_ms = merged[idx]
                next_start, next_end = merged[idx + 1]
                if (next_start - end_ms) < merge_gap_ms:
                    merged[idx] = (merged[idx][0], next_end)
                    del merged[idx + 1]
                    changed = True
                    break

        return merged

    @staticmethod
    def _enforce_min_shot_gap(
        cut_frames: list[int],
        boundary_scores: dict[int, float],
        duration_ms: int,
        fps: float,
        min_gap_frames: int,
    ) -> list[int]:
        if not cut_frames or min_gap_frames <= 1 or fps <= 0:
            return cut_frames

        duration_frame = int(round((duration_ms / 1000.0) * fps))
        boundaries = sorted(set(frame for frame in cut_frames if 0 < frame < duration_frame))
        if len(boundaries) <= 1:
            return boundaries

        def _score(frame_idx: int) -> float:
            return float(boundary_scores.get(frame_idx, 0.0))

        changed = True
        while changed and boundaries:
            changed = False

            if boundaries and boundaries[0] < min_gap_frames:
                del boundaries[0]
                changed = True
                continue

            if boundaries and (duration_frame - boundaries[-1]) < min_gap_frames:
                del boundaries[-1]
                changed = True
                continue

            for idx in range(len(boundaries) - 1):
                left = boundaries[idx]
                right = boundaries[idx + 1]
                if right - left >= min_gap_frames:
                    continue
                if _score(left) < _score(right):
                    del boundaries[idx]
                else:
                    del boundaries[idx + 1]
                changed = True
                break

        return boundaries

    def split_video(
        self,
        scenes: List[Tuple[int, int]],
        progress_callback=None,
        output_indices: Optional[List[int]] = None,
    ) -> List[Optional[str]]:
        """
        使用 FFmpeg 进度监控的视频切分

        Args:
            scenes: List of (start_ms, end_ms) tuples
            progress_callback: 进度回调函数

        Returns:
            与 scenes 对齐的输出文件路径列表（失败项为 None）
        """
        logger.info(f"Task {self.task_id}: 开始视频切分，共 {len(scenes)} 个场景")

        total_scenes = len(scenes)
        output_files: List[Optional[str]] = [None for _ in range(total_scenes)]
        if output_indices is not None and len(output_indices) != total_scenes:
            raise ValueError(
                f"output_indices length mismatch: expected={total_scenes}, actual={len(output_indices)}"
            )

        use_copy = bool(self.processing_config.get("split_copy_mode", False))
        if use_copy:
            logger.info(f"Task {self.task_id}: split_copy_mode=True，使用 copy 模式切分")

        ffmpeg_timeout_sec = max(1, int(getattr(settings, "FFMPEG_PROCESS_TIMEOUT_SEC", 600)))

        for i, (start_ms, end_ms) in enumerate(scenes):
            target_index = output_indices[i] if output_indices is not None else i
            output_file = self.scenes_dir / f"scene_{target_index:03d}.mp4"

            # 创建进度监控器
            def on_scene_progress(progress_info):
                # 场景内进度
                scene_progress = progress_info['progress']

                # 总体进度：10% + (当前场景位置 + 场景内进度) * 40% / 总场景数
                total_progress = 10 + ((i + scene_progress / 100) * 40 / total_scenes)

                if progress_callback:
                    progress_callback(int(total_progress))

            monitor = FFmpegProgressMonitor(on_scene_progress)
            monitor.duration = (end_ms - start_ms) / 1000

            # 转换为 FFmpeg 时间格式 (HH:MM:SS.mmm)
            start_time = self._ms_to_timecode(start_ms)
            duration_sec = (end_ms - start_ms) / 1000.0

            if use_copy:
                cmd = [
                    "ffmpeg",
                    "-ss", start_time,
                    "-i", self.video_path,
                    "-t", str(duration_sec),
                    "-c", "copy",
                    "-progress", "pipe:2",
                    "-v", "quiet",
                    "-y",
                    str(output_file)
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-i", self.video_path,
                    "-ss", start_time,
                    "-t", str(duration_sec),
                    "-progress", "pipe:2",  # 输出进度到 stderr
                    "-v", "quiet",  # 减少日志输出
                    "-c:v", "libx264",
                    "-c:a", "aac",
                    "-y",  # 覆盖输出文件
                    str(output_file)
                ]

            process: subprocess.Popen | None = None
            try:
                # 启动 FFmpeg 并监控进度
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )

                # 在独立线程中监控进度
                monitor_thread = threading.Thread(
                    target=monitor.monitor,
                    args=(process,),
                    daemon=True
                )
                monitor_thread.start()

                # 等待完成
                try:
                    return_code = process.wait(timeout=ffmpeg_timeout_sec)
                except subprocess.TimeoutExpired:
                    monitor.stop()
                    monitor_thread.join(timeout=1)
                    _terminate_subprocess(process)
                    increment_counter("ffmpeg_timeout_total")
                    log_event(
                        logger,
                        logging.WARNING,
                        "ffmpeg_timeout",
                        task_id=self.task_id,
                        stage="split_scene",
                        scene_index=i,
                        timeout_sec=ffmpeg_timeout_sec,
                    )
                    logger.error(
                        "Task %s: 场景 %s 切分超时（>%ss），已终止 FFmpeg 进程",
                        self.task_id,
                        i,
                        ffmpeg_timeout_sec,
                    )
                    continue
                finally:
                    monitor.stop()
                    monitor_thread.join(timeout=1)

                if return_code != 0:
                    stderr_output = ""
                    if process.stderr is not None:
                        try:
                            stderr_output = process.stderr.read()
                        except Exception:
                            stderr_output = ""
                    logger.error(
                        "Task %s: 场景 %s 切分失败 (returncode=%s): %s",
                        self.task_id,
                        i,
                        return_code,
                        (stderr_output or "").strip()[-500:],
                    )
                    _terminate_subprocess(process, wait_timeout_sec=1)
                    continue

                if not output_file.exists() or output_file.stat().st_size <= 0:
                    logger.error(f"Task {self.task_id}: 场景 {i} 切分失败，输出文件为空或不存在")
                    _terminate_subprocess(process, wait_timeout_sec=1)
                    continue

                # copy 模式异常输出检测（文件过小视为失败，回退重编码）
                if use_copy and output_file.stat().st_size < 10240:
                    logger.warning(f"Task {self.task_id}: 场景 {i} copy 输出异常（{output_file.stat().st_size}B），回退重编码")
                    fallback_cmd = [
                        "ffmpeg",
                        "-i", self.video_path,
                        "-ss", start_time,
                        "-t", str(duration_sec),
                        "-c:v", "libx264",
                        "-c:a", "aac",
                        "-y",
                        str(output_file)
                    ]
                    try:
                        fallback_result = subprocess.run(
                            fallback_cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=ffmpeg_timeout_sec,
                            check=False,
                        )
                    except subprocess.TimeoutExpired:
                        increment_counter("ffmpeg_timeout_total")
                        log_event(
                            logger,
                            logging.WARNING,
                            "ffmpeg_timeout",
                            task_id=self.task_id,
                            stage="split_scene_fallback",
                            scene_index=i,
                            timeout_sec=ffmpeg_timeout_sec,
                        )
                        logger.error(
                            "Task %s: 场景 %s 回退重编码超时（>%ss）",
                            self.task_id,
                            i,
                            ffmpeg_timeout_sec,
                        )
                        continue
                    if fallback_result.returncode != 0:
                        logger.error(
                            "Task %s: 场景 %s 回退重编码失败（returncode=%s）",
                            self.task_id,
                            i,
                            fallback_result.returncode,
                        )
                        continue
                    if not output_file.exists() or output_file.stat().st_size <= 0:
                        logger.error(f"Task {self.task_id}: 场景 {i} 回退重编码也失败")
                        continue

                _terminate_subprocess(process, wait_timeout_sec=1)
                output_files[i] = str(output_file)
                logger.info(f"Task {self.task_id}: 场景 {i} 切分完成")

            except subprocess.CalledProcessError as e:
                logger.error(f"Task {self.task_id}: 场景 {i} 切分失败 - {e.stderr}")
                monitor.stop()
                # 继续处理其他场景
                continue
            except Exception as e:
                if process:
                    _terminate_subprocess(process)
                logger.error(f"Task {self.task_id}: 场景 {i} 处理异常 - {str(e)}")
                monitor.stop()
                continue

        success_count = sum(1 for path in output_files if path)
        logger.info(f"Task {self.task_id}: 视频切分完成，成功 {success_count}/{len(scenes)} 个场景")
        return output_files

    def generate_thumbnails_batch(
        self,
        output_files: List[Optional[str]],
        scenes: List[Tuple[int, int]],
        progress_callback=None,
        output_indices: Optional[List[int]] = None,
    ) -> List[Optional[str]]:
        """
        批量生成缩略图，提供平滑进度更新

        Args:
            output_files: 视频文件列表
            scenes: 场景时间列表
            progress_callback: 进度回调函数

        Returns:
            缩略图路径列表（失败为 None）
        """
        thumbnails = []
        total = len(output_files)
        if total == 0:
            return thumbnails
        if output_indices is not None and len(output_indices) != total:
            raise ValueError(
                f"output_indices length mismatch: expected={total}, actual={len(output_indices)}"
            )

        for i, video_file in enumerate(output_files):
            target_index = output_indices[i] if output_indices is not None else i
            thumb_file = self.scenes_dir / f"scene_{target_index:03d}_thumb.jpg"

            # 计算当前进度（50% -> 90%）
            progress = 50 + ((i + 1) * 40 / total)

            # 获取场景时间信息
            scene_duration_ms = scenes[i][1] - scenes[i][0] if i < len(scenes) else 0

            success = False
            if video_file:
                # 仅对成功切分的场景生成缩略图。
                success = self.generate_thumbnail(
                    str(video_file),
                    str(thumb_file),
                    timestamp_ms=None,
                    scene_start_ms=0,
                    scene_duration_ms=scene_duration_ms
                )

            # 每次都更新进度，无论成功失败
            if progress_callback:
                progress_callback(int(progress))

            if success:
                thumbnails.append(str(thumb_file))
            else:
                thumbnails.append(None)  # 保持数组对齐

        return thumbnails

    def generate_thumbnail(
        self,
        video_file: str,
        output_file: str,
        timestamp_ms: Optional[int] = None,
        scene_start_ms: int = 0,
        scene_duration_ms: int = 0
    ) -> bool:
        """
        生成视频缩略图（带重试机制和超时控制）

        Args:
            video_file: 输入视频文件
            output_file: 输出图片文件
            timestamp_ms: 截图时间点（毫秒），None 则自动选择场景 25% 位置
            scene_start_ms: 场景开始时间（毫秒），用于动态时间点计算
            scene_duration_ms: 场景时长（毫秒），用于动态时间点计算

        Returns:
            bool: 是否成功生成
        """
        # 动态选择时间点：场景的 25% 位置
        # 但确保至少有 0.5 秒的偏移，避免黑屏
        if timestamp_ms is None and scene_duration_ms > 0:
            # 这里基于“镜头文件相对时间”取 25%，避免使用全片绝对时间导致越界。
            candidate_ms = int(scene_duration_ms * 0.25)
            upper_bound = max(200, scene_duration_ms - 100)
            timestamp_ms = min(max(200, candidate_ms), upper_bound)
        elif timestamp_ms is None:
            timestamp_ms = 250  # 默认 0.25 秒

        timestamp_sec = timestamp_ms / 1000.0

        # 确保使用绝对路径
        video_file_abs = os.path.abspath(video_file)
        output_file_abs = os.path.abspath(output_file)

        cmd = [
            "ffmpeg",
            "-i", video_file_abs,
            "-ss", str(timestamp_sec),
            "-vframes", "1",
            "-y",
            output_file_abs
        ]

        # 重试机制：质量优先阶段避免无效重试，默认 1 次，最多 3 次。
        max_retries = int(self.processing_config.get("thumbnail_retry", 1))
        max_retries = max(1, min(max_retries, 3))
        timeout = 15  # 15 秒超时（从 5 秒增加，提高成功率）

        for attempt in range(max_retries):
            try:
                logger.debug(f"缩略图生成尝试 {attempt + 1}/{max_retries}: {video_file} -> {output_file}")
                start_time = time.time()
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    check=True,
                    timeout=timeout
                )
                elapsed = time.time() - start_time

                if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                    logger.debug(f"生成缩略图成功: {output_file} (耗时: {elapsed:.2f}s, 尝试: {attempt + 1})")
                    return True
                else:
                    logger.warning(f"缩略图文件为空: {output_file}")

            except subprocess.TimeoutExpired:
                increment_counter("ffmpeg_timeout_total")
                log_event(
                    logger,
                    logging.WARNING,
                    "ffmpeg_timeout",
                    task_id=self.task_id,
                    stage="thumbnail",
                    scene_index=scene_index,
                    timeout_sec=timeout,
                    retry_attempt=attempt + 1,
                )
                logger.warning(f"生成缩略图超时 (> {timeout}s): {output_file} (尝试 {attempt + 1}/{max_retries})")
            except subprocess.CalledProcessError as e:
                stderr_msg = e.stderr.decode() if e.stderr else 'Unknown error'
                logger.warning(f"生成缩略图失败 (尝试 {attempt + 1}/{max_retries}): {stderr_msg}")
                lowered = stderr_msg.lower()
                # 对参数/越界类错误快速失败，避免重复重试浪费时间。
                if "invalid argument" in lowered or "nothing was written into output file" in lowered:
                    logger.warning(f"生成缩略图快速失败: {output_file}")
                    return False
            except Exception as e:
                logger.warning(f"生成缩略图异常 (尝试 {attempt + 1}/{max_retries}): {str(e)}")

            # 最后一次尝试失败，记录错误
            if attempt == max_retries - 1:
                logger.error(f"生成缩略图最终失败: {output_file}")
                return False

        return False

    def process(self, progress_callback=None) -> dict:
        """
        完整的视频处理流程

        Args:
            progress_callback: 进度回调函数，接收进度百分比参数

        Returns:
            处理结果字典
        """
        try:
            # 步骤 1: 场景检测 (0% -> 10%)
            if progress_callback:
                progress_callback(5)
            scenes = self.detect_scenes()

            # 步骤 2: 视频切分 (10% -> 50%)
            if progress_callback:
                progress_callback(10)
            output_files = self.split_video(scenes, progress_callback=progress_callback)

            # 步骤 3: 生成缩略图 (50% -> 90%)
            if progress_callback:
                progress_callback(50)
            thumbnails = self.generate_thumbnails_batch(
                output_files,
                scenes,
                progress_callback=progress_callback
            )

            # 统计失败数量
            failed_count = sum(1 for t in thumbnails if t is None)
            if failed_count > 0:
                logger.warning(
                    f"Task {self.task_id}: {failed_count}/{len(output_files)} 个缩略图生成失败"
                )

            # 完成 (90% -> 100%)
            if progress_callback:
                progress_callback(100)

            return {
                "success": True,
                "scenes_count": len(scenes),
                "output_files": output_files,
                "thumbnails": thumbnails
            }

        except Exception as e:
            logger.error(f"Task {self.task_id}: 处理失败 - {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    def _timecode_to_ms(timecode: str) -> int:
        """将时间码 (HH:MM:SS.mmm) 转换为毫秒"""
        pattern = r"^(\d+):([0-5]\d):([0-5]\d)(?:\.(\d{1,3}))?$"
        match = re.match(pattern, (timecode or "").strip())
        if not match:
            raise ValueError(f"invalid timecode format: {timecode!r}")

        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        ms_raw = match.group(4) or "0"
        milliseconds = int(ms_raw.ljust(3, "0")[:3])

        return (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds

    @staticmethod
    def _ms_to_timecode(ms: int) -> str:
        """将毫秒转换为时间码 (HH:MM:SS.mmm)"""
        total_seconds = ms // 1000
        milliseconds = ms % 1000

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def _get_video_duration_ms(self) -> int:
        """获取视频总时长（毫秒）"""
        timeout_sec = max(1, int(getattr(settings, "FFPROBE_TIMEOUT_SEC", 30)))
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            self.video_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout_sec,
            )
            duration_sec = float(result.stdout.strip())
            return int(duration_sec * 1000)
        except subprocess.TimeoutExpired:
            logger.error("Task %s: ffprobe 获取时长超时（>%ss）", self.task_id, timeout_sec)
            return 0
        except (subprocess.CalledProcessError, ValueError):
            return 0

    def _get_video_fps(self) -> float:
        """获取视频帧率（fps）。"""
        timeout_sec = max(1, int(getattr(settings, "FFPROBE_TIMEOUT_SEC", 30)))
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=avg_frame_rate,r_frame_rate",
            "-of", "default=noprint_wrappers=1:nokey=1",
            self.video_path
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=timeout_sec,
            )
        except subprocess.TimeoutExpired:
            logger.error("Task %s: ffprobe 获取帧率超时（>%ss）", self.task_id, timeout_sec)
            return 0.0
        except subprocess.CalledProcessError:
            return 0.0

        for line in result.stdout.splitlines():
            value = line.strip()
            if not value:
                continue
            if "/" in value:
                left, right = value.split("/", 1)
                try:
                    numerator = float(left)
                    denominator = float(right)
                    if denominator != 0:
                        fps = numerator / denominator
                        if fps > 0:
                            return fps
                except ValueError:
                    continue
            else:
                try:
                    fps = float(value)
                    if fps > 0:
                        return fps
                except ValueError:
                    continue

        return 0.0
