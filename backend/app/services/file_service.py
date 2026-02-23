import shutil
import subprocess
import aiofiles
import logging
import re
from pathlib import Path
from typing import Optional
from fastapi import UploadFile
from app.core.config import settings

logger = logging.getLogger(__name__)


class FileService:
    @staticmethod
    def _sanitize_filename(filename: str | None) -> str:
        """规范化上传文件名，避免路径穿越与非法字符。"""
        normalized = Path(filename or "").name
        normalized = re.sub(r"[\\/\x00-\x1f]", "_", normalized).strip()
        if normalized in {"", ".", ".."}:
            return "upload.bin"
        return normalized

    @staticmethod
    def _split_name_suffix(file_name: str) -> tuple[str, str]:
        """
        拆分“主名 + 扩展名”，支持多扩展名，后缀插入格式为 name_001.ext。
        """
        suffix = "".join(Path(file_name).suffixes)
        if suffix and len(file_name) > len(suffix):
            stem = file_name[:-len(suffix)]
        else:
            stem = file_name
            suffix = ""

        stem = stem.rstrip(" .")
        if not stem:
            stem = "upload"
        return stem, suffix

    @classmethod
    def _build_unique_upload_path(cls, upload_root: Path, safe_name: str) -> Path:
        """按 name, name_001, name_002... 生成上传文件唯一路径。"""
        stem, suffix = cls._split_name_suffix(safe_name)
        counter = 0

        while True:
            if counter == 0:
                candidate = upload_root / f"{stem}{suffix}"
            else:
                candidate = upload_root / f"{stem}_{counter:03d}{suffix}"

            if not candidate.exists():
                return candidate.resolve()
            counter += 1

    @staticmethod
    def to_public_data_path(path_value: str | None) -> str | None:
        """将本地文件路径转换为可访问的 /data 静态路径。"""
        if not path_value:
            return None

        normalized = path_value.replace("\\", "/").strip()
        if not normalized:
            return None

        if normalized.startswith("/data/"):
            return normalized

        if normalized.startswith("./"):
            normalized = normalized[2:]
        if normalized.startswith("data/"):
            return f"/{normalized}"

        parts = [part for part in Path(normalized).parts if part]
        if "data" in parts:
            rel_parts = parts[parts.index("data") + 1:]
            if rel_parts:
                return f"/data/{'/'.join(rel_parts)}"

        return normalized

    @staticmethod
    def validate_video_type(file: UploadFile) -> bool:
        """验证文件类型是否为视频"""
        valid_mime_types = [
            "video/mp4",
            "video/quicktime",
            "video/x-msvideo",
            "video/x-matroska"
        ]
        return file.content_type in valid_mime_types

    @staticmethod
    async def save_upload(file: UploadFile, task_id: str) -> str:
        """保存上传的文件"""
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)

        safe_name = FileService._sanitize_filename(file.filename)
        upload_root = upload_dir.resolve()
        file_path = FileService._build_unique_upload_path(upload_root, safe_name)

        if not (file_path.parent == upload_root or upload_root in file_path.parents):
            raise ValueError("Invalid upload filename")

        max_size = max(0, int(settings.MAX_UPLOAD_SIZE))
        chunk_size = 1024 * 1024  # 1MB
        bytes_written = 0

        try:
            async with aiofiles.open(file_path, "wb") as f:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    bytes_written += len(chunk)
                    if max_size and bytes_written > max_size:
                        raise ValueError(f"File exceeds max size ({max_size} bytes)")
                    await f.write(chunk)
        except Exception:
            file_path.unlink(missing_ok=True)
            raise

        if bytes_written <= 0:
            file_path.unlink(missing_ok=True)
            raise ValueError("Empty upload file")

        return str(file_path)

    @staticmethod
    def build_upload_preview_path(task_id: str) -> Path:
        """构建上传预览图路径，随上传文件一并清理。"""
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir / f"{task_id}_preview.jpg"

    @staticmethod
    def generate_upload_preview(video_path: str, task_id: str) -> Optional[str]:
        """
        上传后立即抽取首帧缩略图。
        失败时返回 None，不阻断上传流程。
        """
        preview_path = FileService.build_upload_preview_path(task_id)
        cmd = [
            "ffmpeg",
            "-ss", "0.5",
            "-i", str(Path(video_path).resolve()),
            "-frames:v", "1",
            "-q:v", "2",
            "-y",
            str(preview_path.resolve()),
        ]

        try:
            subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"生成上传预览图超时: task_id={task_id}")
            return None
        except subprocess.CalledProcessError as exc:
            stderr = (
                exc.stderr.decode(errors="ignore")
                if isinstance(exc.stderr, bytes)
                else str(exc.stderr or "")
            )
            logger.warning(f"生成上传预览图失败: task_id={task_id}, err={stderr}")
            return None
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(f"生成上传预览图异常: task_id={task_id}, err={exc}")
            return None

        if preview_path.exists() and preview_path.stat().st_size > 0:
            return str(preview_path)

        logger.warning(f"上传预览图为空文件: task_id={task_id}")
        return None

    @staticmethod
    def delete_task_files(
        task_id: str,
        task_dir_path: Optional[str] = None,
        upload_file_path: Optional[str] = None,
    ):
        """删除任务相关的所有文件"""
        task_root = Path(settings.TASK_DIR).resolve()

        # 删除按视频名命名的新任务目录（优先）
        if task_dir_path:
            resolved_task_dir = Path(task_dir_path).resolve()
            if task_root == resolved_task_dir or task_root in resolved_task_dir.parents:
                if resolved_task_dir.exists():
                    shutil.rmtree(resolved_task_dir)
            else:
                logger.warning(f"跳过删除非任务目录路径: {resolved_task_dir}")

        # 兜底：根据目录中的 .task_id 标记删除同任务目录
        if task_root.exists():
            for task_dir in task_root.iterdir():
                if not task_dir.is_dir():
                    continue

                marker = task_dir / ".task_id"
                if not marker.exists():
                    continue

                try:
                    marker_task_id = marker.read_text(encoding="utf-8").strip()
                except OSError as exc:
                    logger.warning(f"读取任务标记失败: {marker} ({exc})")
                    continue

                if marker_task_id == task_id and task_dir.exists():
                    shutil.rmtree(task_dir)

        # 兼容删除历史目录（按 task_id 命名）
        legacy_task_dir = task_root / task_id
        if legacy_task_dir.exists():
            shutil.rmtree(legacy_task_dir)

        # 删除原始上传文件（按任务记录精确路径）
        upload_root = Path(settings.UPLOAD_DIR).resolve()
        if upload_file_path:
            upload_path = Path(upload_file_path)
            resolved_upload_path = upload_path.resolve()
            if upload_root == resolved_upload_path.parent or upload_root in resolved_upload_path.parents:
                if resolved_upload_path.exists():
                    resolved_upload_path.unlink()
            else:
                logger.warning(f"跳过删除非上传目录路径: {resolved_upload_path}")

        # 删除上传预览图
        preview_path = FileService.build_upload_preview_path(task_id).resolve()
        if upload_root == preview_path.parent or upload_root in preview_path.parents:
            preview_path.unlink(missing_ok=True)

    @staticmethod
    def delete_split_assets(task_id: str, keep_task_dir_path: Optional[str] = None):
        """
        删除指定任务的切片产物目录（TASK_DIR 下），保留上传源文件。

        Args:
            task_id: 任务 ID
            keep_task_dir_path: 需要保留的任务目录（通常是本轮最新切分目录）
        """
        task_root = Path(settings.TASK_DIR).resolve()
        if not task_root.exists():
            return

        keep_path = Path(keep_task_dir_path).resolve() if keep_task_dir_path else None

        for task_dir in task_root.iterdir():
            if not task_dir.is_dir():
                continue

            resolved_dir = task_dir.resolve()
            if keep_path and resolved_dir == keep_path:
                continue

            marker = task_dir / ".task_id"
            should_delete = False

            if marker.exists():
                try:
                    marker_task_id = marker.read_text(encoding="utf-8").strip()
                except OSError as exc:
                    logger.warning(f"读取任务标记失败: {marker} ({exc})")
                    continue
                should_delete = marker_task_id == task_id
            else:
                # 兼容历史按 task_id 命名的目录。
                should_delete = task_dir.name == task_id

            if should_delete and task_dir.exists():
                shutil.rmtree(task_dir)
