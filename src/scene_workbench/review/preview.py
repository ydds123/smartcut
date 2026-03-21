from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from scene_workbench.models import BoundaryCandidate, VideoSource


class PreviewFrame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    frame: int
    second: float


class BoundaryPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    boundary_id: str
    boundary_type: str
    start_frame: int
    end_frame: int
    recommended_cut_frame: int
    context_frames: list[PreviewFrame]
    evidence_summary: list[str]


def _to_second(frame: int, fps: float) -> float:
    return round(frame / fps, 3) if fps > 0 else 0.0


def build_boundary_preview(
    video: VideoSource,
    boundary: BoundaryCandidate,
    *,
    context_padding: int = 12,
) -> BoundaryPreview:
    frame_points = [
        ("context_before", max(0, boundary.start_frame - context_padding)),
        ("start", boundary.start_frame),
    ]
    if boundary.end_frame > boundary.start_frame:
        frame_points.append(("mid", (boundary.start_frame + boundary.end_frame) // 2))
        frame_points.append(("end", boundary.end_frame))
    else:
        frame_points.append(("recommended", boundary.recommended_cut_frame))
    frame_points.append(
        ("context_after", min(video.total_frames - 1, boundary.end_frame + context_padding))
    )

    preview_frames = [
        PreviewFrame(label=label, frame=frame, second=_to_second(frame, video.fps))
        for label, frame in frame_points
    ]

    evidence_summary: list[str] = []
    evidence = boundary.detector_evidence
    if evidence.pyscenedetect is not None:
        for detector_name in ("content", "adaptive", "threshold"):
            detector = getattr(evidence.pyscenedetect, detector_name)
            if detector and detector.triggered:
                score_text = ""
                if detector.score is not None:
                    score_text = f" score={detector.score}"
                evidence_summary.append(f"pyscenedetect:{detector_name}{score_text}")
    if evidence.transnetv2 is not None and evidence.transnetv2.triggered:
        evidence_summary.append(
            f"transnetv2 score={evidence.transnetv2.score} window={evidence.transnetv2.window_id}"
        )
    if evidence.manual_review is not None and evidence.manual_review.triggered:
        evidence_summary.append(
            f"manual_review:{evidence.manual_review.decision}"
        )

    return BoundaryPreview(
        boundary_id=boundary.id,
        boundary_type=boundary.boundary_type,
        start_frame=boundary.start_frame,
        end_frame=boundary.end_frame,
        recommended_cut_frame=boundary.recommended_cut_frame,
        context_frames=preview_frames,
        evidence_summary=evidence_summary,
    )
