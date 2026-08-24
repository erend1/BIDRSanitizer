import { afterEach, describe, expect, it, vi } from "vitest";

import { ReviewApiClient } from "./api-client";
import { syntheticSession } from "./test/fixtures";

describe("ReviewApiClient", () => {
  const token = "a".repeat(32);

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("rejects short, whitespace, and non-ASCII launch tokens", () => {
    expect(() => new ReviewApiClient("too-short")).toThrow(/format is invalid/i);
    expect(() => new ReviewApiClient(`${"a".repeat(31)} `)).toThrow(/format is invalid/i);
    expect(() => new ReviewApiClient(`İ${"a".repeat(31)}`)).toThrow(/format is invalid/i);
  });

  it("uploads raw image bytes without sending a filename or token in the URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(syntheticSession()), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const client = new ReviewApiClient(token);
    const file = new File([new Uint8Array([1, 2, 3])], "private-name.png", {
      type: "image/png",
    });

    await client.createSession(file);

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(url).toBe("/api/v1/review-sessions");
    expect(url).not.toContain(token);
    expect(headers.get("X-BIDR-API-Token")).toBe(token);
    expect(headers.get("Content-Type")).toBe("image/png");
    expect(headers.get("Content-Disposition")).toBeNull();
    expect(init.body).toBe(file);
    expect(init.cache).toBe("no-store");
  });

  it("uses authenticated no-store requests for sensitive previews", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(new Blob([new Uint8Array([1])], { type: "image/png" }), {
        status: 200,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await new ReviewApiClient(token).getSource("session / one");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/review-sessions/session%20%2F%20one/source");
    expect(new Headers(init.headers).get("X-BIDR-API-Token")).toBe(
      token,
    );
    expect(init.cache).toBe("no-store");
  });

  it("surfaces only the bounded API detail on failures", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "x".repeat(400), private: "ignored" }), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      new ReviewApiClient(token).getSession("session"),
    ).rejects.toMatchObject({
      status: 422,
      message: "x".repeat(240),
    });
  });

  it("marks best-effort unload cleanup as keepalive", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await new ReviewApiClient(token).deleteSession("session", true);

    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      method: "DELETE",
      keepalive: true,
      cache: "no-store",
    });
  });
});
