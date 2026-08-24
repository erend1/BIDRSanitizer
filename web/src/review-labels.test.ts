import { describe, expect, it } from "vitest";

import { exportStatusPresentation } from "./review-labels";

describe("export status presentation", () => {
  it("keeps a human override distinct from an ordinary pass", () => {
    const status = exportStatusPresentation("verified_with_human_overrides");

    expect(status.tone).toBe("caution");
    expect(status.title).toMatch(/with overrides/i);
    expect(status.description).toMatch(/kept visible/i);
  });

  it("does not label a review-required artifact as safe", () => {
    const status = exportStatusPresentation("review_required");

    expect(status.tone).toBe("danger");
    expect(status.downloadLabel).toBe("Download review artifact");
    expect(status.description).toMatch(/must not be represented or shared/i);
  });

  it("scopes a clear detector result without promising anonymization", () => {
    const status = exportStatusPresentation("passed");

    expect(status.description).toMatch(/not a legal guarantee/i);
  });
});
