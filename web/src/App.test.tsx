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

    fireEvent.click(screen.getByRole("button", { name: /save all & export/i }));

    expect(
      await screen.findByRole("heading", { name: /detectors are clear, with overrides/i }),
    ).toBeInTheDocument();
    const planCall = fetchMock.mock.calls.find(
      ([url, init]) => String(url).endsWith("/plan") && init?.method === "PATCH",
    );
    expect(planCall).toBeDefined();
    expect(JSON.parse(String(planCall?.[1]?.body))).toEqual({
      page_number: 1,
      expected_revision: 0,
      decisions: [{ region_id: "auto-0001", action: "remove" }],
      geometry_updates: [],
      manual_regions: [],
    });
    await waitFor(() =>
      expect(screen.getByText(/removed auto boxes/i)).toBeInTheDocument(),
    );
  });

  it("uploads a PDF, analyzes every page, and navigates authenticated previews", async () => {
    window.__BIDR_RUNTIME__ = { apiToken: "a".repeat(32) };
    const firstPlan = syntheticPlan({ plan_id: "pdf-page-1" });
    const secondPlan = syntheticPlan({ plan_id: "pdf-page-2" });
    const uploaded = syntheticSession({
      media_type: "application/pdf",
      page_count: 2,
      pages: [
        { page_number: 1, image_width: 200, image_height: 120, plan: null, export: null },
        { page_number: 2, image_width: 200, image_height: 120, plan: null, export: null },
      ],
    });
    const analyzed = syntheticSession({
      state: "analyzed",
      media_type: "application/pdf",
      page_count: 2,
      pages: [
        { page_number: 1, image_width: 200, image_height: 120, plan: firstPlan, export: null },
        { page_number: 2, image_width: 200, image_height: 120, plan: secondPlan, export: null },
      ],
    });

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/review-sessions") && init?.method === "POST") {
        return jsonResponse(uploaded, 201);
      }
      if (url.endsWith("/analysis")) return jsonResponse(analyzed);
      if (url.includes("/pages/") && url.endsWith("/source")) {
        return new Response(new Blob([new Uint8Array([1])], { type: "image/png" }));
      }
      throw new Error(`Unexpected test request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:pdf-page-preview");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => undefined);

    const { container } = render(<App />);
    const fileInput = container.querySelector<HTMLInputElement>('input[type="file"]');
    fireEvent.change(fileInput!, {
      target: { files: [new File([new Uint8Array([37, 80, 68, 70])], "local.pdf")] },
    });
    fireEvent.click(screen.getByRole("button", { name: /begin analysis/i }));

    const pageSelect = await screen.findByRole("combobox", { name: /pdf page/i });
    expect(pageSelect).toHaveValue("1");
    fireEvent.change(pageSelect, { target: { value: "2" } });
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).endsWith("/pages/2/source"),
        ),
      ).toBe(true),
    );
  });
});
