import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import type { ReviewSession } from "./api-types";
import {
  syntheticExport,
  syntheticPlan,
  syntheticSession,
} from "./test/fixtures";

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("App review workflow", () => {
  afterEach(() => {
    window.__BIDR_RUNTIME__ = {};
    vi.unstubAllGlobals();
  });

  it("keeps an automatic removal explicit through save and verified export", async () => {
    window.__BIDR_RUNTIME__ = { apiToken: "a".repeat(32) };
    const plan = syntheticPlan();
    const uploaded = syntheticSession();
    const analyzed = syntheticSession({
      state: "analyzed",
      plan,
    });
    const revisedPlan = syntheticPlan({
      revision: 1,
      regions: plan.regions.map((region) => ({ ...region, action: "remove" })),
    });
    const revised = syntheticSession({
      state: "analyzed",
      plan: revisedPlan,
    });
    const completed: ReviewSession = syntheticSession({
      state: "exported",
      plan: revisedPlan,
      export: syntheticExport({
        status: "verified_with_human_overrides",
        detectors_clear: true,
        passed: false,
        plan_revision: 1,
        automatic_removal_count: 1,
        applied_region_count: 0,
      }),
    });

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/review-sessions") && init?.method === "POST") {
        return jsonResponse(uploaded, 201);
      }
      if (url.endsWith("/source")) {
        return new Response(new Blob([new Uint8Array([1, 2, 3])], { type: "image/png" }));
      }
      if (url.endsWith("/analysis")) {
        return jsonResponse(analyzed);
      }
      if (url.endsWith("/plan") && init?.method === "PATCH") {
        return jsonResponse(revised);
      }
      if (url.endsWith("/export") && init?.method === "POST") {
        return jsonResponse(completed);
      }
      if (url.endsWith("/export") && (init?.method === undefined || init.method === "GET")) {
        return new Response(
          new Blob([new Uint8Array([4, 5, 6])], { type: "image/png" }),
          {
            headers: {
              "X-BIDR-Verification-Status": "verified_with_human_overrides",
            },
          },
        );
      }
      throw new Error(`Unexpected test request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:synthetic-preview");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

    const { container } = render(<App />);
    const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]');
    expect(fileInput).not.toBeNull();
    fireEvent.change(fileInput!, {
      target: {
        files: [new File([new Uint8Array([1])], "not-sent.png", { type: "image/png" })],
      },
    });
    fireEvent.click(screen.getByRole("button", { name: /begin analysis/i }));

    expect(
      await screen.findByRole("heading", { name: /review every proposed region/i }),
    ).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: /keep visible · override/i }),
    );
    expect(screen.getByText(/1 human override/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /save & export/i }));

    expect(
      await screen.findByRole("heading", { name: /detectors are clear, with overrides/i }),
    ).toBeInTheDocument();
    const planCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/plan") && init?.method === "PATCH",
    );
    expect(planCall).toBeDefined();
    expect(JSON.parse(String(planCall?.[1]?.body))).toEqual({
      expected_revision: 0,
      decisions: [{ region_id: "auto-0001", action: "remove" }],
      manual_regions: [],
    });
    await waitFor(() =>
      expect(screen.getByText(/human overrides/i)).toBeInTheDocument(),
    );
  });
});
