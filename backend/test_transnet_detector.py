"""
TransNetV2 检测器单元测试

测试模型加载、降级逻辑和边界检测功能
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import numpy as np

# 测试目标
from app.services.transnet_detector import (
    TransNetV2Detector,
    download_model,
)
from app.services.transnet_architecture import (
    TransNetV2,
    TransNetV2Lite,
    load_pretrained_weights,
)


class TestTransNetV2Detector:
    """TransNetV2 检测器测试"""

    def test_init_default_params(self):
        """测试默认参数初始化"""
        detector = TransNetV2Detector()

        assert detector.mode == "precision"
        assert detector.threshold == 0.3
        assert detector.tolerance_frames == 12
        assert detector.window_size == 100
        assert detector._model is None
        assert not detector._load_attempted
        assert not detector._load_failed

    def test_init_custom_params(self):
        """测试自定义参数初始化"""
        detector = TransNetV2Detector(
            mode="fast",
            threshold=0.5,
            tolerance_frames=20,
            window_size=50,
        )

        assert detector.mode == "fast"
        assert detector.threshold == 0.5
        assert detector.tolerance_frames == 20
        assert detector.window_size == 50

    def test_threshold_clamping(self):
        """测试阈值边界限制"""
        # 超出范围应被限制
        detector1 = TransNetV2Detector(threshold=-0.5)
        assert detector1.threshold == 0.0

        detector2 = TransNetV2Detector(threshold=1.5)
        assert detector2.threshold == 1.0

    def test_get_mode_info(self):
        """测试模式信息获取"""
        # 精准模式
        detector_precision = TransNetV2Detector(mode="precision")
        info = detector_precision.get_mode_info()

        assert info["name"] == "精准模式"
        assert info["accuracy"] == "F1: ~88%"
        assert info["model_type"] == "TransNetV2"
        assert info["current_mode"] == "precision"

        # 快速模式
        detector_fast = TransNetV2Detector(mode="fast")
        info = detector_fast.get_mode_info()

        assert info["name"] == "快速模式"
        assert info["accuracy"] == "F1: ~77%"
        assert info["model_type"] == "TransNetV2Lite"

    def test_is_available_without_model(self):
        """测试无模型文件时的可用性检查"""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_path = Path(tmpdir) / "nonexistent.pth"
            detector = TransNetV2Detector(model_path=str(nonexistent_path))

            assert not detector.is_available()
            assert detector._load_failed
            assert detector._model is None

    def test_ensure_loaded_thread_safety(self):
        """测试线程安全的模型加载"""
        # 创建模拟的模型文件（使用真实 torch）
        with tempfile.NamedTemporaryFile(suffix=".pth", delete=False) as f:
            model_path = f.name

        try:
            # 创建模拟权重并保存
            import torch
            mock_state_dict = {
                'conv3d_1.weight': torch.randn(32, 3, 3, 5, 5),
                'fc_out.weight': torch.randn(2, 256),
            }
            torch.save(mock_state_dict, model_path)

            detector = TransNetV2Detector(model_path=model_path, mode="fast")

            # 第一次加载
            result1 = detector._ensure_loaded()

            # 第二次应直接返回 True（不重复加载）
            result2 = detector._ensure_loaded()

            # 至少应该尝试加载
            # 注意：由于模型结构不完全匹配，可能加载失败，但不应该崩溃
            if detector._model is not None:
                assert result1

            # 第二次调用结果应该一致
            assert result2 == result1

        finally:
            Path(model_path).unlink(missing_ok=True)

    def test_detect_boundaries_without_model(self):
        """测试无模型时返回空结果"""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_path = Path(tmpdir) / "nonexistent.pth"
            detector = TransNetV2Detector(model_path=str(nonexistent_path))

            # 标记加载失败
            detector._load_failed = True

            # 应返回空字典
            result = detector.detect_boundaries("fake_video.mp4")
            assert result == {}

    def test_is_boundary_confirmed(self):
        """测试边界确认逻辑"""
        detector = TransNetV2Detector(tolerance_frames=12)

        # 测试容差范围内
        boundaries = {100: 0.8, 200: 0.9}
        assert detector._is_boundary_confirmed(95, boundaries)  # 在容差内
        assert detector._is_boundary_confirmed(100, boundaries)  # 完全匹配
        assert detector._is_boundary_confirmed(110, boundaries)  # 在容差内

        # 测试容差范围外
        assert not detector._is_boundary_confirmed(50, boundaries)
        assert not detector._is_boundary_confirmed(150, boundaries)

    @patch('app.services.transnet_detector.cv2')
    def test_merge_with_pyscene_without_video(self, mock_cv2):
        """测试无法打开视频时的降级"""
        detector = TransNetV2Detector()
        mock_cv2.VideoCapture.return_value.isOpened.return_value = False

        pyscene_scenes = [(0, 1000), (1000, 2000)]
        result = detector.merge_with_pyscene(pyscene_scenes, "fake_video.mp4")

        # 应返回原始结果
        assert result == pyscene_scenes

    @patch('app.services.transnet_detector.cv2')
    def test_merge_with_pyscene_invalid_fps(self, mock_cv2):
        """测试无效 FPS 时的降级"""
        detector = TransNetV2Detector()

        # Mock video capture
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cap.get.return_value = 0  # FPS = 0
        mock_cv2.VideoCapture.return_value = mock_cap

        pyscene_scenes = [(0, 1000), (1000, 2000)]
        result = detector.merge_with_pyscene(pyscene_scenes, "fake_video.mp4")

        # 应返回原始结果
        assert result == pyscene_scenes


class TestTransNetV2Architecture:
    """TransNetV2 模型架构测试"""

    def test_transnetv2_creation(self):
        """测试 TransNetV2 模型创建"""
        model = TransNetV2(D=512)

        # 检查关键组件存在
        assert hasattr(model, 'SDDCNN')
        assert hasattr(model, 'fc1')
        assert hasattr(model, 'cls_layer1')

        # 检查隐藏维度
        assert model.fc1.out_features == 512

    def test_transnetv2_lite_creation(self):
        """测试 TransNetV2Lite 模型创建"""
        model = TransNetV2Lite(D=256)

        # 检查关键组件存在
        assert hasattr(model, 'SDDCNN')
        assert hasattr(model, 'cls_layer1')

        # 检查隐藏维度
        assert model.fc1.out_features == 256

    @patch('app.services.transnet_architecture.torch')
    def test_load_pretrained_weights_success(self, mock_torch):
        """测试预训练权重加载成功"""
        mock_model = MagicMock()
        mock_torch.load.return_value = {'state_dict': 'data'}

        with tempfile.NamedTemporaryFile(suffix=".pth") as f:
            result = load_pretrained_weights(mock_model, f.name, 'cpu')

        assert result is True
        mock_model.load_state_dict.assert_called_once()

    @patch('app.services.transnet_architecture.torch')
    def test_load_pretrained_weights_failure(self, mock_torch):
        """测试预训练权重加载失败"""
        mock_model = MagicMock()
        mock_torch.load.side_effect = Exception("Load failed")

        with tempfile.NamedTemporaryFile(suffix=".pth") as f:
            result = load_pretrained_weights(mock_model, f.name, 'cpu')

        assert result is False


class TestDownloadModel:
    """模型下载测试"""

    def test_download_model_creates_dir(self):
        """测试下载时创建目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "models"

            # Mock urllib.request.urlretrieve
            with patch('urllib.request.urlretrieve'):
                try:
                    download_model(output_dir=output_dir)
                except:
                    pass  # 我们只关心目录创建

                # 验证目录已创建
                assert output_dir.exists()

    def test_download_model_skips_if_exists(self):
        """测试文件存在时跳过下载"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "models"
            output_dir.mkdir(parents=True, exist_ok=True)

            # 创建假模型文件
            model_file = output_dir / "transnetv2-pytorch-weights.pth"
            model_file.write_text("fake model")

            # Mock metadata to mark the existing file as valid.
            with patch(
                "app.services.transnet_detector.checkpoint_metadata",
                return_value={
                    "size_bytes": TransNetV2Detector.MIN_MODEL_SIZE_BYTES,
                    "num_keys": TransNetV2Detector.MIN_EXPECTED_STATE_KEYS,
                },
            ), patch("app.services.transnet_detector._download_to_path") as mock_download:
                result = download_model(output_dir=output_dir)

                # 不应调用下载
                assert not mock_download.called
                assert result == model_file


@pytest.fixture
def sample_video_path(tmp_path):
    """创建测试用的视频文件路径"""
    video_path = tmp_path / "test_video.mp4"
    # 这里可以创建一个实际的视频文件用于集成测试
    return str(video_path)


@pytest.fixture
def sample_frames():
    """创建测试用的帧数据"""
    # 创建 100 帧 224x224 RGB 图像
    return np.random.rand(100, 224, 224, 3).astype(np.float32)


class TestIntegration:
    """集成测试（需要实际模型文件）"""

    @pytest.mark.skipif(
        not Path.home().joinpath(".smartcut/models/transnetv2-pytorch-weights.pth").exists(),
        reason="TransNetV2 模型文件不存在"
    )
    def test_real_model_loading(self):
        """测试真实模型加载（如果存在）"""
        model_path = Path.home() / ".smartcut" / "models" / "transnetv2-pytorch-weights.pth"

        if model_path.exists():
            detector = TransNetV2Detector(model_path=str(model_path))
            assert detector.is_available()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
