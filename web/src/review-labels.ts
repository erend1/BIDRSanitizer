import type {
  DetectionType,
  ReviewedOutputStatus,
  ReviewRegion,
} from "./api-types";

export const detectionLabels: Record<DetectionType, string> = {
  tckn: "Identity number",
  phone: "Phone number",
  email: "Email address",
  person: "Person name",
  address: "Postal address",
  face: "Face",
  signature: "Signature",
};

export function regionLabel(region: ReviewRegion): string {
  if (region.detection_type !== null) {
    return detectionLabels[region.detection_type];
  }

  return region.provenance === "manual" ? "Manual privacy region" : "Detection";
}

export interface StatusPresentation {
  eyebrow: string;
  title: string;
  description: string;
  tone: "clear" | "caution" | "danger";
  downloadLabel: string;
}

export function exportStatusPresentation(
  status: ReviewedOutputStatus,
): StatusPresentation {
  if (status === "passed") {
    return {
      eyebrow: "Verification complete",
      title: "Configured detectors are clear",
      description:
        "The exported pixels were scanned again and no remaining detections were found. This is not a legal guarantee that every sensitive item was identified.",
      tone: "clear",
      downloadLabel: "Download reviewed output",
    };
  }

  if (status === "verified_with_human_overrides") {
    return {
      eyebrow: "Human override recorded",
      title: "Detectors are clear, with overrides",
      description:
        "The exported pixels scanned clear, but one or more automatic regions were deliberately kept visible. Review those decisions before sharing the output.",
      tone: "caution",
      downloadLabel: "Download output with overrides",
    };
  }

  return {
    eyebrow: "Further review required",
    title: "Detections remain in the output",
    description:
      "The verifier still found sensitive regions after export. This artifact must not be represented or shared as verified safe output.",
    tone: "danger",
    downloadLabel: "Download review artifact",
  };
}
