export type BoundaryType =
  | "hard_cut"
  | "dissolve"
  | "fade_in"
  | "fade_out"
  | "wipe"
  | "unknown";

export type ReviewState =
  | "unreviewed"
  | "accepted"
  | "rejected"
  | "adjusted"
  | "merged"
  | "inserted";

export type ReviewActionType =
  | "accept"
  | "reject"
  | "adjust"
  | "merge"
  | "insert";

export interface VideoSource {
  path: string;
  fps: number;
  width: number;
  height: number;
  total_frames: number;
  duration_sec: number;
}

export interface PySceneDetectEvidence {
  triggered: boolean;
  score?: number | null;
  scores?: number[];
  detector?: string;
}

export interface TransNetV2Evidence {
  triggered: boolean;
  score?: number;
  window_id?: string;
}

export interface ManualReviewEvidence {
  triggered: boolean;
  decision: ReviewActionType | string;
  reason?: string;
}

export interface DetectorEvidence {
  pyscenedetect?: {
    content?: PySceneDetectEvidence;
    adaptive?: PySceneDetectEvidence;
    threshold?: PySceneDetectEvidence;
  };
  transnetv2?: TransNetV2Evidence;
  manual_review?: ManualReviewEvidence;
  [key: string]: unknown;
}

export interface BoundaryCandidate {
  id: string;
  start_frame: number;
  end_frame: number;
  recommended_cut_frame: number;
  boundary_type: BoundaryType;
  confidence: number;
  review_state: ReviewState;
  detector_evidence: DetectorEvidence;
  notes?: string[];
  source_boundary_ids?: string[];
}

export interface SuspiciousWindow {
  id: string;
  start_frame: number;
  end_frame: number;
  reason:
    | "coarse_candidate"
    | "low_confidence"
    | "long_scene"
    | "gradual_suspect"
    | string;
  source_boundary_ids: string[];
}

export interface ReviewActionPayload {
  old_start_frame?: number;
  old_end_frame?: number;
  old_recommended_cut_frame?: number;
  new_start_frame?: number;
  new_end_frame?: number;
  new_recommended_cut_frame?: number;
  merged_start_frame?: number;
  merged_end_frame?: number;
  merged_recommended_cut_frame?: number;
  merged_boundary_type?: BoundaryType;
  start_frame?: number;
  end_frame?: number;
  recommended_cut_frame?: number;
  boundary_type?: BoundaryType;
  reason?: string;
  [key: string]: unknown;
}

export interface ReviewAction {
  id: string;
  action: ReviewActionType;
  target_boundary_ids: string[];
  result_boundary_id: string | null;
  created_by: string;
  created_at: string;
  payload: ReviewActionPayload;
}

export interface ReviewActionCommand {
  action: ReviewActionType;
  target_boundary_ids: string[];
  created_by: string;
  payload: ReviewActionPayload;
}

export interface ConfigSection {
  [key: string]: unknown;
}

export interface ManifestConfig {
  coarse_detection?: ConfigSection;
  refinement?: ConfigSection;
  fusion?: ConfigSection;
  review?: ConfigSection;
  export?: ConfigSection;
  [key: string]: unknown;
}

export interface ManifestSummary {
  counts: {
    coarse_boundaries: number;
    suspicious_windows: number;
    refined_boundaries: number;
    final_boundaries: number;
    accepted: number;
    adjusted: number;
    merged: number;
    inserted: number;
    rejected: number;
  };
}

export interface ProjectManifest {
  version: string;
  manifest_id: string;
  video: VideoSource;
  config: ManifestConfig;
  coarse_boundaries: BoundaryCandidate[];
  suspicious_windows: SuspiciousWindow[];
  refined_boundaries: BoundaryCandidate[];
  final_boundaries: BoundaryCandidate[];
  review_actions: ReviewAction[];
  summary?: ManifestSummary;
}
