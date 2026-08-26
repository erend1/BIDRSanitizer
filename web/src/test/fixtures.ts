import type { ReviewPlan, ReviewSession, ReviewedExport } from "../api-types";

export function syntheticPlan(
  overrides: Partial<ReviewPlan> = {},
): ReviewPlan {
  return {
    plan_id: "plan-synthetic",
    revision: 0,
    image_width: 200,
    image_height: 120,
    settings: {
      redaction_margin: 5,
      max_redaction_passes: 3,
    },
    regions: [
      {
        region_id: "auto-0001",
        bbox: { x1: 20, y1: 25, x2: 70, y2: 50 },
        provenance: "automatic",
        action: "retain",
        detection_type: "face",
        confidence: 0.9,
      },
    ],
    ...overrides,
  };
}

export function syntheticExport(
  overrides: Partial<ReviewedExport> = {},
): ReviewedExport {
  return {
    status: "passed",
    detectors_clear: true,
    passed: true,
    plan_revision: 0,
    redaction_passes: 1,
    automatic_removal_count: 0,
    manual_addition_count: 0,
    applied_region_count: 1,
    remaining_detections: [],
    remediation_detections: [],
    ...overrides,
  };
}

export function syntheticSession(
  overrides: Partial<ReviewSession> = {},
): ReviewSession {
  return {
    session_id: "session-synthetic",
    state: "uploaded",
    media_type: "image/png",
    image_width: 200,
    image_height: 120,
    plan: null,
    export: null,
    ...overrides,
  };
}
