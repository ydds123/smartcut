from __future__ import annotations

from datetime import datetime, timezone

from scene_workbench.models import (
    BoundaryCandidate,
    DetectorEvidence,
    ManualReviewEvidence,
    ProjectManifest,
    ReviewAction,
    ReviewActionCommand,
    ReviewActionPayload,
    build_manifest_summary,
)


class ReviewActionError(RuntimeError):
    """Raised when a review action is invalid."""


def _next_action_id(manifest: ProjectManifest) -> str:
    return f"a_{len(manifest.review_actions) + 1:04d}"


def _next_boundary_id(manifest: ProjectManifest) -> str:
    numeric_ids = []
    for boundary in manifest.final_boundaries:
        if boundary.id.startswith("f_"):
            try:
                numeric_ids.append(int(boundary.id.split("_", 1)[1]))
            except ValueError:
                continue
    return f"f_{(max(numeric_ids, default=0) + 1):04d}"


def _sorted_boundaries(boundaries: list[BoundaryCandidate]) -> list[BoundaryCandidate]:
    return sorted(
        boundaries,
        key=lambda item: (item.start_frame, item.end_frame, item.recommended_cut_frame, item.id),
    )


def _manual_review_evidence(command: ReviewActionCommand) -> ManualReviewEvidence:
    return ManualReviewEvidence(
        triggered=True,
        decision=command.action,
        reason=command.payload.reason,
    )


def _with_manual_review(
    boundary: BoundaryCandidate,
    command: ReviewActionCommand,
) -> BoundaryCandidate:
    next_boundary = boundary.model_copy(deep=True)
    next_boundary.detector_evidence.manual_review = _manual_review_evidence(command)
    return next_boundary


def _validate_targets(
    command: ReviewActionCommand,
    boundary_map: dict[str, BoundaryCandidate],
) -> None:
    targets = command.target_boundary_ids
    if command.action == "insert":
        if targets:
            raise ReviewActionError("`insert` must not include target_boundary_ids.")
        return

    if not targets:
        raise ReviewActionError(f"`{command.action}` requires target_boundary_ids.")

    missing = [target_id for target_id in targets if target_id not in boundary_map]
    if missing:
        raise ReviewActionError(f"Unknown target boundaries: {', '.join(missing)}")

    if command.action in {"accept", "reject", "adjust"} and len(targets) != 1:
        raise ReviewActionError(f"`{command.action}` requires exactly 1 target boundary.")
    if command.action == "merge" and len(targets) < 2:
        raise ReviewActionError("`merge` requires at least 2 target boundaries.")


def _validate_payload(command: ReviewActionCommand) -> None:
    payload = command.payload
    if command.action == "adjust":
        required = [
            payload.new_start_frame,
            payload.new_end_frame,
            payload.new_recommended_cut_frame,
        ]
        if any(value is None for value in required):
            raise ReviewActionError(
                "`adjust` requires new_start_frame, new_end_frame and new_recommended_cut_frame."
            )
    elif command.action == "merge":
        required = [
            payload.merged_start_frame,
            payload.merged_end_frame,
            payload.merged_recommended_cut_frame,
            payload.merged_boundary_type,
        ]
        if any(value is None for value in required):
            raise ReviewActionError(
                "`merge` requires merged_start_frame, merged_end_frame, merged_recommended_cut_frame and merged_boundary_type."
            )
    elif command.action == "insert":
        required = [
            payload.start_frame,
            payload.end_frame,
            payload.recommended_cut_frame,
            payload.boundary_type,
        ]
        if any(value is None for value in required):
            raise ReviewActionError(
                "`insert` requires start_frame, end_frame, recommended_cut_frame and boundary_type."
            )


def _build_review_log(
    manifest: ProjectManifest,
    command: ReviewActionCommand,
    result_boundary_id: str | None,
) -> ReviewAction:
    return ReviewAction(
        id=_next_action_id(manifest),
        action=command.action,
        target_boundary_ids=list(command.target_boundary_ids),
        result_boundary_id=result_boundary_id,
        created_by=command.created_by,
        created_at=datetime.now(timezone.utc),
        payload=command.payload.model_copy(deep=True),
    )


def _recompute_summary(manifest: ProjectManifest):
    return build_manifest_summary(
        coarse_boundaries=manifest.coarse_boundaries,
        suspicious_windows=manifest.suspicious_windows,
        refined_boundaries=manifest.refined_boundaries,
        final_boundaries=manifest.final_boundaries,
        review_actions=manifest.review_actions,
    )


def _apply_accept(
    manifest: ProjectManifest,
    command: ReviewActionCommand,
    boundary_map: dict[str, BoundaryCandidate],
) -> str:
    target_id = command.target_boundary_ids[0]
    updated: list[BoundaryCandidate] = []
    for boundary in manifest.final_boundaries:
        if boundary.id != target_id:
            updated.append(boundary)
            continue
        accepted = _with_manual_review(boundary, command)
        accepted.review_state = "accepted"
        updated.append(accepted)
    manifest.final_boundaries = _sorted_boundaries(updated)
    return target_id


def _apply_reject(
    manifest: ProjectManifest,
    command: ReviewActionCommand,
) -> None:
    target_id = command.target_boundary_ids[0]
    manifest.final_boundaries = [
        boundary for boundary in manifest.final_boundaries if boundary.id != target_id
    ]


def _apply_adjust(
    manifest: ProjectManifest,
    command: ReviewActionCommand,
) -> str:
    target_id = command.target_boundary_ids[0]
    updated: list[BoundaryCandidate] = []
    for boundary in manifest.final_boundaries:
        if boundary.id != target_id:
            updated.append(boundary)
            continue
        adjusted = _with_manual_review(boundary, command)
        adjusted.start_frame = command.payload.new_start_frame  # type: ignore[assignment]
        adjusted.end_frame = command.payload.new_end_frame  # type: ignore[assignment]
        adjusted.recommended_cut_frame = command.payload.new_recommended_cut_frame  # type: ignore[assignment]
        adjusted.review_state = "adjusted"
        if command.payload.reason:
            adjusted.notes.append(command.payload.reason)
        updated.append(adjusted)
    manifest.final_boundaries = _sorted_boundaries(updated)
    return target_id


def _merge_detector_evidence(boundaries: list[BoundaryCandidate], command: ReviewActionCommand) -> DetectorEvidence:
    merged = DetectorEvidence()
    for boundary in boundaries:
        if merged.pyscenedetect is None and boundary.detector_evidence.pyscenedetect is not None:
            merged.pyscenedetect = boundary.detector_evidence.pyscenedetect.model_copy(deep=True)
        if merged.transnetv2 is None and boundary.detector_evidence.transnetv2 is not None:
            merged.transnetv2 = boundary.detector_evidence.transnetv2.model_copy(deep=True)
        merged.extra.update(boundary.detector_evidence.extra)
    merged.manual_review = _manual_review_evidence(command)
    return merged


def _apply_merge(
    manifest: ProjectManifest,
    command: ReviewActionCommand,
    boundary_map: dict[str, BoundaryCandidate],
) -> str:
    targets = [boundary_map[target_id] for target_id in command.target_boundary_ids]
    merged_boundary = BoundaryCandidate(
        id=_next_boundary_id(manifest),
        start_frame=command.payload.merged_start_frame,  # type: ignore[arg-type]
        end_frame=command.payload.merged_end_frame,  # type: ignore[arg-type]
        recommended_cut_frame=command.payload.merged_recommended_cut_frame,  # type: ignore[arg-type]
        boundary_type=command.payload.merged_boundary_type,  # type: ignore[arg-type]
        confidence=max(boundary.confidence for boundary in targets),
        review_state="merged",
        detector_evidence=_merge_detector_evidence(targets, command),
        notes=[note for boundary in targets for note in boundary.notes],
        source_boundary_ids=list(
            dict.fromkeys(
                source_id
                for boundary in targets
                for source_id in ([boundary.id] + boundary.source_boundary_ids)
            )
        ),
    )
    if command.payload.reason:
        merged_boundary.notes.append(command.payload.reason)

    manifest.final_boundaries = _sorted_boundaries(
        [
            boundary
            for boundary in manifest.final_boundaries
            if boundary.id not in command.target_boundary_ids
        ]
        + [merged_boundary]
    )
    return merged_boundary.id


def _apply_insert(
    manifest: ProjectManifest,
    command: ReviewActionCommand,
) -> str:
    inserted_boundary = BoundaryCandidate(
        id=_next_boundary_id(manifest),
        start_frame=command.payload.start_frame,  # type: ignore[arg-type]
        end_frame=command.payload.end_frame,  # type: ignore[arg-type]
        recommended_cut_frame=command.payload.recommended_cut_frame,  # type: ignore[arg-type]
        boundary_type=command.payload.boundary_type,  # type: ignore[arg-type]
        confidence=1.0,
        review_state="inserted",
        detector_evidence=DetectorEvidence(
            manual_review=_manual_review_evidence(command),
        ),
        notes=[command.payload.reason] if command.payload.reason else [],
        source_boundary_ids=[],
    )
    manifest.final_boundaries = _sorted_boundaries(
        [*manifest.final_boundaries, inserted_boundary]
    )
    return inserted_boundary.id


def apply_review_action(
    manifest: ProjectManifest,
    command: ReviewActionCommand | dict,
) -> ProjectManifest:
    next_manifest = manifest.model_copy(deep=True)
    next_command = (
        command
        if isinstance(command, ReviewActionCommand)
        else ReviewActionCommand.model_validate(command)
    )
    boundary_map = {boundary.id: boundary for boundary in next_manifest.final_boundaries}

    _validate_targets(next_command, boundary_map)
    _validate_payload(next_command)

    result_boundary_id: str | None
    if next_command.action == "accept":
        result_boundary_id = _apply_accept(next_manifest, next_command, boundary_map)
    elif next_command.action == "reject":
        _apply_reject(next_manifest, next_command)
        result_boundary_id = None
    elif next_command.action == "adjust":
        result_boundary_id = _apply_adjust(next_manifest, next_command)
    elif next_command.action == "merge":
        result_boundary_id = _apply_merge(next_manifest, next_command, boundary_map)
    elif next_command.action == "insert":
        result_boundary_id = _apply_insert(next_manifest, next_command)
    else:  # pragma: no cover
        raise ReviewActionError(f"Unsupported action: {next_command.action}")

    next_manifest.review_actions.append(
        _build_review_log(next_manifest, next_command, result_boundary_id)
    )
    next_manifest.summary = _recompute_summary(next_manifest)
    return next_manifest
