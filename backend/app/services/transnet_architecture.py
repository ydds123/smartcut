"""TransNetV2 model definitions aligned with the official PyTorch inference implementation."""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as functional

logger = logging.getLogger(__name__)


class TransNetV2(nn.Module):
    """Official TransNetV2 architecture used by inference-pytorch."""

    def __init__(
        self,
        F: int = 16,
        L: int = 3,
        S: int = 2,
        D: int = 1024,
        use_many_hot_targets: bool = True,
        use_frame_similarity: bool = True,
        use_color_histograms: bool = True,
        use_mean_pooling: bool = False,
        dropout_rate: float | None = 0.5,
        use_convex_comb_reg: bool = False,
        use_resnet_features: bool = False,
        use_resnet_like_top: bool = False,
        frame_similarity_on_last_layer: bool = False,
    ):
        super().__init__()

        if use_resnet_features or use_resnet_like_top or use_convex_comb_reg or frame_similarity_on_last_layer:
            raise NotImplementedError("Unsupported TransNetV2 options in PyTorch inference path")

        self.SDDCNN = nn.ModuleList(
            [StackedDDCNNV2(in_filters=3, n_blocks=S, filters=F, stochastic_depth_drop_prob=0.0)]
            + [StackedDDCNNV2(in_filters=(F * 2 ** (i - 1)) * 4, n_blocks=S, filters=F * 2 ** i) for i in range(1, L)]
        )

        self.frame_sim_layer = (
            FrameSimilarity(
                sum([(F * 2 ** i) * 4 for i in range(L)]), lookup_window=101, output_dim=128, similarity_dim=128,
                use_bias=True
            )
            if use_frame_similarity
            else None
        )
        self.color_hist_layer = ColorHistograms(lookup_window=101, output_dim=128) if use_color_histograms else None
        self.dropout = nn.Dropout(dropout_rate) if dropout_rate is not None else None

        output_dim = ((F * 2 ** (L - 1)) * 4) * 3 * 6
        if use_frame_similarity:
            output_dim += 128
        if use_color_histograms:
            output_dim += 128

        self.fc1 = nn.Linear(output_dim, D)
        self.cls_layer1 = nn.Linear(D, 1)
        self.cls_layer2 = nn.Linear(D, 1) if use_many_hot_targets else None

        self.use_mean_pooling = use_mean_pooling
        self.eval()

    def forward(self, inputs: torch.Tensor) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]] | torch.Tensor:
        assert isinstance(inputs, torch.Tensor) and list(inputs.shape[2:]) == [27, 48, 3] and inputs.dtype == torch.uint8, (
            "Input must be uint8 with shape [B, T, 27, 48, 3]"
        )

        x = inputs.permute([0, 4, 1, 2, 3]).float().div_(255.0)

        block_features = []
        for block in self.SDDCNN:
            x = block(x)
            block_features.append(x)

        if self.use_mean_pooling:
            x = torch.mean(x, dim=[3, 4])
            x = x.permute(0, 2, 1)
        else:
            x = x.permute(0, 2, 3, 4, 1)
            x = x.reshape(x.shape[0], x.shape[1], -1)

        if self.frame_sim_layer is not None:
            x = torch.cat([self.frame_sim_layer(block_features), x], dim=2)

        if self.color_hist_layer is not None:
            x = torch.cat([self.color_hist_layer(inputs), x], dim=2)

        x = functional.relu(self.fc1(x))

        if self.dropout is not None:
            x = self.dropout(x)

        one_hot = self.cls_layer1(x)
        if self.cls_layer2 is not None:
            return one_hot, {"many_hot": self.cls_layer2(x)}
        return one_hot


class TransNetV2Lite(TransNetV2):
    """Backwards-compatible alias; keeps the same architecture for weight compatibility."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class StackedDDCNNV2(nn.Module):
    def __init__(
        self,
        in_filters: int,
        n_blocks: int,
        filters: int,
        shortcut: bool = True,
        use_octave_conv: bool = False,
        pool_type: str = "avg",
        stochastic_depth_drop_prob: float = 0.0,
    ):
        super().__init__()

        if use_octave_conv:
            raise NotImplementedError("Octave convolution is not supported")

        if pool_type not in {"max", "avg"}:
            raise ValueError("pool_type must be 'max' or 'avg'")

        self.shortcut = shortcut
        self.DDCNN = nn.ModuleList(
            [
                DilatedDCNNV2(
                    in_filters if i == 1 else filters * 4,
                    filters,
                    octave_conv=use_octave_conv,
                    activation=functional.relu if i != n_blocks else None,
                )
                for i in range(1, n_blocks + 1)
            ]
        )
        self.pool = nn.MaxPool3d(kernel_size=(1, 2, 2)) if pool_type == "max" else nn.AvgPool3d(kernel_size=(1, 2, 2))
        self.stochastic_depth_drop_prob = stochastic_depth_drop_prob

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        x = inputs
        shortcut = None

        for block in self.DDCNN:
            x = block(x)
            if shortcut is None:
                shortcut = x

        x = functional.relu(x)

        if self.shortcut is not None:
            if self.stochastic_depth_drop_prob != 0.0:
                if self.training:
                    if random.random() < self.stochastic_depth_drop_prob:
                        x = shortcut
                    else:
                        x = x + shortcut
                else:
                    x = (1 - self.stochastic_depth_drop_prob) * x + shortcut
            else:
                x += shortcut

        return self.pool(x)


class DilatedDCNNV2(nn.Module):
    def __init__(
        self,
        in_filters: int,
        filters: int,
        batch_norm: bool = True,
        activation=None,
        octave_conv: bool = False,
    ):
        super().__init__()

        if octave_conv:
            raise NotImplementedError("Octave convolution is not supported")

        self.Conv3D_1 = Conv3DConfigurable(in_filters, filters, 1, use_bias=not batch_norm)
        self.Conv3D_2 = Conv3DConfigurable(in_filters, filters, 2, use_bias=not batch_norm)
        self.Conv3D_4 = Conv3DConfigurable(in_filters, filters, 4, use_bias=not batch_norm)
        self.Conv3D_8 = Conv3DConfigurable(in_filters, filters, 8, use_bias=not batch_norm)

        self.bn = nn.BatchNorm3d(filters * 4, eps=1e-3) if batch_norm else None
        self.activation = activation

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        conv1 = self.Conv3D_1(inputs)
        conv2 = self.Conv3D_2(inputs)
        conv3 = self.Conv3D_4(inputs)
        conv4 = self.Conv3D_8(inputs)

        x = torch.cat([conv1, conv2, conv3, conv4], dim=1)

        if self.bn is not None:
            x = self.bn(x)

        if self.activation is not None:
            x = self.activation(x)

        return x


class Conv3DConfigurable(nn.Module):
    def __init__(
        self,
        in_filters: int,
        filters: int,
        dilation_rate: int,
        separable: bool = True,
        octave: bool = False,
        use_bias: bool = True,
        kernel_initializer=None,
    ):
        super().__init__()

        if octave:
            raise NotImplementedError("Octave convolution is not supported")
        if kernel_initializer is not None:
            raise NotImplementedError("Custom kernel initializers are not supported")

        if separable:
            conv1 = nn.Conv3d(
                in_filters,
                2 * filters,
                kernel_size=(1, 3, 3),
                dilation=(1, 1, 1),
                padding=(0, 1, 1),
                bias=False,
            )
            conv2 = nn.Conv3d(
                2 * filters,
                filters,
                kernel_size=(3, 1, 1),
                dilation=(dilation_rate, 1, 1),
                padding=(dilation_rate, 0, 0),
                bias=use_bias,
            )
            self.layers = nn.ModuleList([conv1, conv2])
        else:
            conv = nn.Conv3d(
                in_filters,
                filters,
                kernel_size=3,
                dilation=(dilation_rate, 1, 1),
                padding=(dilation_rate, 1, 1),
                bias=use_bias,
            )
            self.layers = nn.ModuleList([conv])

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        x = inputs
        for layer in self.layers:
            x = layer(x)
        return x


class FrameSimilarity(nn.Module):
    def __init__(
        self,
        in_filters: int,
        similarity_dim: int = 128,
        lookup_window: int = 101,
        output_dim: int = 128,
        stop_gradient: bool = False,
        use_bias: bool = False,
    ):
        super().__init__()

        if stop_gradient:
            raise NotImplementedError("Stop gradient is not supported")

        self.projection = nn.Linear(in_filters, similarity_dim, bias=use_bias)
        self.fc = nn.Linear(lookup_window, output_dim)

        self.lookup_window = lookup_window
        if lookup_window % 2 != 1:
            raise ValueError("lookup_window must be odd")

    def forward(self, inputs: list[torch.Tensor]) -> torch.Tensor:
        x = torch.cat([torch.mean(item, dim=[3, 4]) for item in inputs], dim=1)
        x = torch.transpose(x, 1, 2)

        x = self.projection(x)
        x = functional.normalize(x, p=2, dim=2)

        batch_size, time_window = x.shape[0], x.shape[1]
        similarities = torch.bmm(x, x.transpose(1, 2))
        similarities_padded = functional.pad(similarities, [(self.lookup_window - 1) // 2, (self.lookup_window - 1) // 2])

        batch_indices = torch.arange(0, batch_size, device=x.device).view([batch_size, 1, 1]).repeat(
            [1, time_window, self.lookup_window]
        )
        time_indices = torch.arange(0, time_window, device=x.device).view([1, time_window, 1]).repeat(
            [batch_size, 1, self.lookup_window]
        )
        lookup_indices = torch.arange(0, self.lookup_window, device=x.device).view([1, 1, self.lookup_window]).repeat(
            [batch_size, time_window, 1]
        ) + time_indices

        similarities = similarities_padded[batch_indices, time_indices, lookup_indices]
        return functional.relu(self.fc(similarities))


class ColorHistograms(nn.Module):
    def __init__(self, lookup_window: int = 101, output_dim: int | None = None):
        super().__init__()

        self.fc = nn.Linear(lookup_window, output_dim) if output_dim is not None else None
        self.lookup_window = lookup_window
        if lookup_window % 2 != 1:
            raise ValueError("lookup_window must be odd")

    @staticmethod
    def compute_color_histograms(frames: torch.Tensor) -> torch.Tensor:
        frames = frames.int()

        def get_bin(f: torch.Tensor) -> torch.Tensor:
            r, g, b = f[:, :, 0], f[:, :, 1], f[:, :, 2]
            r, g, b = r >> 5, g >> 5, b >> 5
            return (r << 6) + (g << 3) + b

        batch_size, time_window, height, width, channels = frames.shape
        if channels != 3:
            raise ValueError("Input must have 3 channels")

        frames_flat = frames.view(batch_size * time_window, height * width, 3)

        binned_values = get_bin(frames_flat)
        frame_bin_prefix = (torch.arange(0, batch_size * time_window, device=frames.device) << 9).view(-1, 1)
        binned_values = (binned_values + frame_bin_prefix).view(-1)

        histograms = torch.zeros(batch_size * time_window * 512, dtype=torch.int32, device=frames.device)
        histograms.scatter_add_(0, binned_values, torch.ones(len(binned_values), dtype=torch.int32, device=frames.device))

        histograms = histograms.view(batch_size, time_window, 512).float()
        return functional.normalize(histograms, p=2, dim=2)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        x = self.compute_color_histograms(inputs)

        batch_size, time_window = x.shape[0], x.shape[1]
        similarities = torch.bmm(x, x.transpose(1, 2))
        similarities_padded = functional.pad(similarities, [(self.lookup_window - 1) // 2, (self.lookup_window - 1) // 2])

        batch_indices = torch.arange(0, batch_size, device=x.device).view([batch_size, 1, 1]).repeat(
            [1, time_window, self.lookup_window]
        )
        time_indices = torch.arange(0, time_window, device=x.device).view([1, time_window, 1]).repeat(
            [batch_size, 1, self.lookup_window]
        )
        lookup_indices = torch.arange(0, self.lookup_window, device=x.device).view([1, 1, self.lookup_window]).repeat(
            [batch_size, time_window, 1]
        ) + time_indices

        similarities = similarities_padded[batch_indices, time_indices, lookup_indices]

        if self.fc is not None:
            return functional.relu(self.fc(similarities))
        return similarities


def _extract_state_dict(payload: Any) -> Dict[str, torch.Tensor]:
    if isinstance(payload, dict):
        if "model_state_dict" in payload and isinstance(payload["model_state_dict"], dict):
            return payload["model_state_dict"]
        if "state_dict" in payload and isinstance(payload["state_dict"], dict):
            return payload["state_dict"]
        return payload
    raise ValueError("Unsupported checkpoint payload format")


def normalize_state_dict_keys(state_dict: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
    normalized: Dict[str, torch.Tensor] = {}
    for key, value in state_dict.items():
        if key.startswith("module."):
            normalized[key[len("module."):]] = value
        else:
            normalized[key] = value
    return normalized


def load_pretrained_weights(model: nn.Module, weights_path: str, device: torch.device) -> bool:
    """Load checkpoint with best-effort compatibility handling."""
    try:
        payload = torch.load(weights_path, map_location=device, weights_only=False)
        state_dict = normalize_state_dict_keys(_extract_state_dict(payload))
        incompatible = model.load_state_dict(state_dict, strict=False)
        if incompatible.missing_keys:
            logger.warning("TransNetV2 missing keys: %s", incompatible.missing_keys[:10])
        if incompatible.unexpected_keys:
            logger.warning("TransNetV2 unexpected keys: %s", incompatible.unexpected_keys[:10])
        logger.info("Loaded TransNetV2 checkpoint: %s", weights_path)
        return True
    except Exception as exc:
        logger.error("Failed to load TransNetV2 checkpoint %s: %s", weights_path, exc)
        return False


def predict_sliding_window(
    model: nn.Module,
    frames: torch.Tensor,
    window_size: int = 100,
    device: torch.device = torch.device("cpu"),
) -> Tuple[torch.Tensor, torch.Tensor]:
    """Backward-compatible helper kept for existing imports."""
    model.eval()
    model.to(device)

    if frames.ndim != 4:
        raise ValueError("frames must be [T, H, W, C]")

    input_np = frames.detach().cpu().numpy().astype(np.uint8)
    input_np = np.ascontiguousarray(input_np)

    if len(input_np) == 0:
        return torch.empty(0), torch.empty(0)

    window_size = max(4, int(window_size))
    if window_size % 2 == 1:
        window_size += 1

    stride = max(1, window_size // 2)
    context = (window_size - stride) // 2
    remainder = len(input_np) % stride
    pad_end = context + (stride - remainder if remainder != 0 else 0)

    start = np.repeat(input_np[:1], context, axis=0)
    end = np.repeat(input_np[-1:], pad_end, axis=0)
    padded = np.concatenate([start, input_np, end], axis=0)

    single_parts: list[np.ndarray] = []
    many_parts: list[np.ndarray] = []

    with torch.no_grad():
        ptr = 0
        while ptr + window_size <= len(padded):
            window = padded[ptr:ptr + window_size]
            ptr += stride

            inp = torch.from_numpy(window[np.newaxis]).to(device=device, dtype=torch.uint8)
            outputs = model(inp)
            if isinstance(outputs, tuple):
                single_logits, many_logits_dict = outputs
                many_logits = many_logits_dict["many_hot"]
            else:
                single_logits = outputs
                many_logits = outputs

            single_prob = torch.sigmoid(single_logits)[0, context:context + stride, 0].cpu().numpy()
            many_prob = torch.sigmoid(many_logits)[0, context:context + stride, 0].cpu().numpy()
            single_parts.append(single_prob)
            many_parts.append(many_prob)

    single = np.concatenate(single_parts, axis=0)[:len(input_np)] if single_parts else np.empty(0, dtype=np.float32)
    many = np.concatenate(many_parts, axis=0)[:len(input_np)] if many_parts else np.empty(0, dtype=np.float32)

    return torch.from_numpy(single), torch.from_numpy(many)


def checkpoint_metadata(weights_path: str) -> dict[str, Any]:
    """Lightweight checkpoint metadata for validation and diagnostics."""
    path = Path(weights_path)
    if not path.exists():
        return {"exists": False, "size_bytes": 0, "num_keys": 0, "keys_sample": []}

    size_bytes = path.stat().st_size
    try:
        payload = torch.load(str(path), map_location="cpu", weights_only=False)
        state_dict = normalize_state_dict_keys(_extract_state_dict(payload))
        keys = list(state_dict.keys())
    except Exception:
        return {"exists": True, "size_bytes": size_bytes, "num_keys": 0, "keys_sample": []}

    return {
        "exists": True,
        "size_bytes": size_bytes,
        "num_keys": len(keys),
        "keys_sample": keys[:10],
    }
