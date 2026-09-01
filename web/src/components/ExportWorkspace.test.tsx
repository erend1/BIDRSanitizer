import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { syntheticExport } from "../test/fixtures";
import { ExportWorkspace } from "./ExportWorkspace";

function renderResult(status: "passed" | "verified_with_human_overrides" | "review_required") {
  render(
    <ExportWorkspace
      result={syntheticExport({
        status,
        passed: status === "passed",
        detectors_clear: status !== "review_required",
        automatic_removal_count:
          status === "verified_with_human_overrides" ? 1 : 0,
      })}
      exportUrl={null}
      mediaType="image/png"
      imageWidth={200}
      imageHeight={120}
      pageCount={1}
      busyLabel={null}
      onDownload={vi.fn()}
      onContinueReview={vi.fn()}
      onAddRemaining={vi.fn()}
      onStartNew={vi.fn()}
    />,
  );
}

describe("ExportWorkspace", () => {
  it("presents automatic passes with detector scope", () => {
    renderResult("passed");

    expect(
      screen.getByRole("heading", { name: /configured detectors are clear/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/not a legal guarantee/i)).toBeInTheDocument();
  });

  it("presents human overrides as a caution state", () => {
    renderResult("verified_with_human_overrides");

    expect(screen.getByRole("heading", { name: /with overrides/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /download output with overrides/i }),
    ).toBeInTheDocument();
  });

  it("labels an unresolved output only as a review artifact", () => {
    renderResult("review_required");

    expect(screen.getByRole("heading", { name: /detections remain/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /download review artifact/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/verified safe output$/i)).not.toBeInTheDocument();
  });
});
