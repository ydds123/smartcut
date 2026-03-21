"""Fusion / decision 规则实现。"""

from __future__ import annotations

from dataclasses import dataclass

from scene_workbench.config import WorkbenchConfig, coerce_config
from scene_workbench.models import BoundaryCandidate, DetectorEvidence


@dataclass(slots=True)
class WorkingBoundary:
    start_frame: int
    end_frame: int
    recommended_cut_frame: int
    boundary_type: str
    confidence: float
    detector_evidence: DetectorEvidence
    source_boundary_ids: list[str]
    notes: list[str]


def _is_gradual(boundary: BoundaryCandidate | WorkingBoundary) -> bool:
    return boundary.boundary_type != "hard_cut" or boundary.end_frame > boundary.start_frame


def _interval_distance(
    left: BoundaryCandidate | WorkingBoundary,
    right: BoundaryCandidate | WorkingBoundary,
) -> int:
    if right.start_frame > left.end_frame:
        return right.start_frame - left.end_frame
    if left.start_frame > right.end_frame:
        return left.start_frame - right.end_frame
    return 0


def _merge_detector_evidence(
    coarse_candidates: list[BoundaryCandidate],
    refined_candidate: BoundaryCandidate | None,
) -> DetectorEvidence:
    pyscenedetect = None
    manual_review = None
    if coarse_candidates:
        pyscenedetect = coarse_candidates[0].detector_evidence.pyscenedetect
        manual_review = coarse_candidates[0].detector_evidence.manual_review
    transnetv2 = refined_candidate.detector_evidence.transnetv2 if refined_candidate else None

    return DetectorEvidence(
        pyscenedetect=pyscenedetect,
        transnetv2=transnetv2,
        manual_review=manual_review,
    )


def _build_working_boundary(
    coarse_candidates: list[BoundaryCandidate],
    refined_candidate: BoundaryCandidate | None,
    config: WorkbenchConfig,
) -> WorkingBoundary:
    if refined_candidate is not None:
        start_frame = refined_candidate.start_frame
        end_frame = refined_candidate.end_frame
        boundary_type = refined_candidate.boundary_type
        confidence = refined_candidate.confidence
        recommended_cut_frame = refined_candidate.recommended_cut_frame
        notes = list(refined_candidate.notes)
    else:
        best_coarse = max(coarse_candidates, key=lambda item: item.confidence)
        start_frame = best_coarse.start_frame
        end_frame = best_coarse.end_frame
        boundary_type = best_coarse.boundary_type
        confidence = best_coarse.confidence
        recommended_cut_frame = best_coarse.recommended_cut_frame
        notes = list(best_coarse.notes)

    if refined_candidate is not None and _is_gradual(refined_candidate):
        start_frame = min(
            [refined_candidate.start_frame, *[item.start_frame for item in coarse_candidates]]
        )
        end_frame = max(
            [refined_candidate.end_frame, *[item.end_frame for item in coarse_candidates]]
        )
        recommended_cut_frame = refined_candidate.recommended_cut_frame
        confidence = max(
            [refined_candidate.confidence, *[item.confidence for item in coarse_candidates]]
        )
    elif refined_candidate is not None and coarse_candidates:
        best_coarse = max(coarse_candidates, key=lambda item: item.confidence)
        start_frame = min(best_coarse.start_frame, refined_candidate.start_frame)
        end_frame = max(best_coarse.end_frame, refined_candidate.end_frame)
        confidence = max(best_coarse.confidence, refined_candidate.confidence)
        recommended_cut_frame = refined_candidate.recommended_cut_frame

    if refined_candidate is None and boundary_type == "unknown" and len(coarse_candidates) > 1:
        boundary_type = "hard_cut"

    if boundary_type != "hard_cut" and recommended_cut_frame == start_frame == end_frame:
        recommended_cut_frame = (start_frame + end_frame) // 2

    source_boundary_ids: list[str] = []
    for item in coarse_candidates:
        if item.id not in source_boundary_ids:
            source_boundary_ids.append(item.id)
    if refined_candidate and refined_candidate.id not in source_boundary_ids:
        source_boundary_ids.append(refined_candidate.id)

    return WorkingBoundary(
        start_frame=start_frame,
        end_frame=end_frame,
        recommended_cut_frame=recommended_cut_frame,
        boundary_type=boundary_type,
        confidence=min(max(confidence, 0.0), 1.0),
        detector_evidence=_merge_detector_evidence(coarse_candidates, refined_candidate),
        source_boundary_ids=source_boundary_ids,
        notes=notes,
    )


def _collapse_neighbors(
    boundaries: list[WorkingBoundary],
    config: WorkbenchConfig,
) -> list[WorkingBoundary]:
    if not boundaries:
        return []

    boundaries = sorted(
        boundaries,
        key=lambda item: (item.start_frame, item.end_frame, item.recommended_cut_frame),
    )
    collapsed: list[WorkingBoundary] = [boundaries[0]]

    for current in boundaries[1:]:
        previous = collapsed[-1]
        if _interval_distance(previous, current) > config.fusion.merge_gap_frames:
            collapsed.append(current)
            continue

        if _is_gradual(previous) or _is_gradual(current):
            previous.start_frame = min(previous.start_frame, current.start_frame)
            previous.end_frame = max(previous.end_frame, current.end_frame)
            previous.boundary_type = (
                previous.boundary_type
                if previous.boundary_type != "hard_cut"
                else current.boundary_type
            )
            previous.recommended_cut_frame = (
                previous.start_frame + previous.end_frame
            ) // 2
        elif current.confidence > previous.confidence:
            previous.start_frame = current.start_frame
            previous.end_frame = current.end_frame
            previous.recommended_cut_frame = current.recommended_cut_frame
            previous.boundary_type = current.boundary_type

        previous.confidence = max(previous.confidence, current.confidence)
        for source_id in current.source_boundary_ids:
            if source_id not in previous.source_boundary_ids:
                previous.source_boundary_ids.append(source_id)
        previous.notes.extend(note for note in current.notes if note not in previous.notes)
        if current.detector_evidence.transnetv2 is not None:
            previous.detector_evidence.transnetv2 = current.detector_evidence.transnetv2
        if (
            previous.detector_evidence.pyscenedetect is None
            and current.detector_evidence.pyscenedetect is not None
        ):
            previous.detector_evidence.pyscenedetect = current.detector_evidence.pyscenedetect

    return collapsed


def fuse_boundaries(
    coarse_boundaries: list[BoundaryCandidate],
    refined_boundaries: list[BoundaryCandidate],
    config: WorkbenchConfig | dict | None = None,
) -> list[BoundaryCandidate]:
    """按规则合并 coarse / refined，输出 final boundaries。"""
    workbench_config = coerce_config(config)
    remaining_coarse = sorted(
        coarse_boundaries,
        key=lambda item: (item.start_frame, item.end_frame, item.recommended_cut_frame),
    )
    working_boundaries: list[WorkingBoundary] = []

    for refined_candidate in sorted(
        refined_boundaries,
        key=lambda item: (item.start_frame, item.end_frame, item.recommended_cut_frame),
    ):
        nearby: list[BoundaryCandidate] = []
        survivors: list[BoundaryCandidate] = []
        for coarse_candidate in remaining_coarse:
            if (
                _interval_distance(coarse_candidate, refined_candidate)
                <= workbench_config.fusion.merge_gap_frames
            ):
                nearby.append(coarse_candidate)
            else:
                survivors.append(coarse_candidate)
        remaining_coarse = survivors
        working_boundaries.append(
            _build_working_boundary(nearby, refined_candidate, workbench_config)
        )

    for coarse_candidate in remaining_coarse:
        working_boundaries.append(
            _build_working_boundary([coarse_candidate], None, workbench_config)
        )

    collapsed = _collapse_neighbors(working_boundaries, workbench_config)
    final_boundaries: list[BoundaryCandidate] = []
    for index, boundary in enumerate(collapsed, start=1):
        final_boundaries.append(
            BoundaryCandidate(
                id=f"f_{index:04d}",
                start_frame=boundary.start_frame,
                end_frame=boundary.end_frame,
                recommended_cut_frame=boundary.recommended_cut_frame,
                boundary_type=boundary.boundary_type,  # type: ignore[arg-type]
                confidence=boundary.confidence,
                review_state="unreviewed",
                detector_evidence=boundary.detector_evidence,
                notes=boundary.notes,
                source_boundary_ids=boundary.source_boundary_ids,
            )
        )

    return final_boundaries
