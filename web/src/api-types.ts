export const detectionTypes = [
  "tckn",
  "phone",
  "email",
  "person",
  "address",
  "face",
  "signature",
] as const;

export type DetectionType = (typeof detectionTypes)[number];
export type ReviewAction = "retain" | "remove";
export type RegionProvenance = "automatic" | "manual";
export type ReviewSessionState = "uploaded" | "analyzed" | "exported";
export type ReviewedOutputStatus =
  | "passed"
  | "verified_with_human_overrides"
  | "review_required";

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface ImageSettings {
  redaction_margin: number;
  max_redaction_passes: number;
}

export interface ReviewRegion {
  region_id: string;
  bbox: BoundingBox;
  provenance: RegionProvenance;
  action: ReviewAction;
  detection_type: DetectionType | null;
  confidence: number | null;
  geometry_modified: boolean;
}

export interface Detection {
  detection_type: DetectionType;
  bbox: BoundingBox;
  confidence: number;
}

export interface ReviewPlan {
  plan_id: string;
  revision: number;
  image_width: number;
  image_height: number;
  settings: ImageSettings;
  regions: ReviewRegion[];
}

export interface ReviewedExport {
  status: ReviewedOutputStatus;
  detectors_clear: boolean;
  passed: boolean;
  plan_revision: number;
  redaction_passes: number;
  automatic_removal_count: number;
  automatic_geometry_adjustment_count: number;
  manual_addition_count: number;
  applied_region_count: number;
  text_layer_empty: boolean | null;
  page_count: number;
  pages: ReviewedPageExport[];
  page_revisions: PageRevision[];
  remaining_detections: PageDetection[];
  remediation_detections: PageDetection[];
}

export interface ReviewedPageExport {
  status: ReviewedOutputStatus;
  detectors_clear: boolean;
  passed: boolean;
  plan_revision: number;
  redaction_passes: number;
  automatic_removal_count: number;
  automatic_geometry_adjustment_count: number;
  manual_addition_count: number;
  applied_region_count: number;
  remaining_detections: Detection[];
  remediation_detections: Detection[];
}

export interface PageDetection extends Detection {
  page_number: number;
}

export interface PageRevision {
  page_number: number;
  revision: number;
}

export interface ReviewPage {
  page_number: number;
  image_width: number;
  image_height: number;
  plan: ReviewPlan | null;
  export: ReviewedPageExport | null;
}

export interface ReviewSession {
  session_id: string;
  state: ReviewSessionState;
  media_type: "image/png" | "image/jpeg" | "application/pdf";
  page_count: number;
  pages: ReviewPage[];
  image_width: number;
  image_height: number;
  plan: ReviewPlan | null;
  export: ReviewedExport | null;
}

export interface ReviewDecision {
  region_id: string;
  action: ReviewAction;
}

export interface ManualRegionRequest {
  bbox: BoundingBox;
  detection_type: DetectionType | null;
}

export interface ReviewGeometryUpdate {
  region_id: string;
  bbox: BoundingBox;
}

export interface RevisePlanRequest {
  page_number: number;
  expected_revision: number;
  decisions: ReviewDecision[];
  geometry_updates: ReviewGeometryUpdate[];
  manual_regions: ManualRegionRequest[];
}

export interface HealthResponse {
  status: string;
  api_version: string;
}
