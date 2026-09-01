import type {
  ReviewPlan,
  ReviewSession,
  ReviewedExport,
  ReviewedPageExport,
} from "../api-types";

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
        geometry_modified: false,
      },
    ],
    ...overrides,
  };
}

export function syntheticExport(
  overrides: Partial<ReviewedExport> = {},
): ReviewedExport {
  const pageExport: ReviewedPageExport = {
    status: "passed",
    detectors_clear: true,
    passed: true,
    plan_revision: 0,
    redaction_passes: 1,
    automatic_removal_count: 0,
    automatic_geometry_adjustment_count: 0,
    manual_addition_count: 0,
    applied_region_count: 1,
    remaining_detections: [],
    remediation_detections: [],
  };
  return {
    ...pageExport,
    text_layer_empty: null,
    page_count: 1,
    pages: [pageExport],
    page_revisions: [{ page_number: 1, revision: 0 }],
    remaining_detections: [],
    remediation_detections: [],
    ...overrides,
  };
}

export function syntheticSession(
  overrides: Partial<ReviewSession> = {},
): ReviewSession {
  const plan = overrides.plan ?? null;
  const exported = overrides.export ?? null;
  return {
    session_id: "session-synthetic",
    state: "uploaded",
    media_type: "image/png",
    page_count: 1,
    image_width: 200,
    image_height: 120,
    plan: null,
    export: null,
    ...overrides,
    pages: overrides.pages ?? [
      {
        page_number: 1,
        image_width: overrides.image_width ?? 200,
        image_height: overrides.image_height ?? 120,
        plan,
        export: exported?.pages[0] ?? null,
      },
    ],
  };
}
