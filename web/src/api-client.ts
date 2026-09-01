import type {
  HealthResponse,
  ImageSettings,
  PageRevision,
  RevisePlanRequest,
  ReviewSession,
  ReviewedOutputStatus,
} from "./api-types";

const API_PREFIX = "/api/v1";
const API_TOKEN_HEADER = "X-BIDR-API-Token";

export function isValidLaunchToken(token: string): boolean {
  return (
    token.length >= 32 &&
    /^[\x00-\x7F]+$/.test(token) &&
    !/\s/.test(token)
  );
}

export class InvalidLaunchTokenError extends Error {
  constructor() {
    super("The launch token format is invalid.");
    this.name = "InvalidLaunchTokenError";
  }
}

function safeErrorDetail(value: unknown): string | null {
  if (
    typeof value === "object" &&
    value !== null &&
    "detail" in value &&
    typeof value.detail === "string"
  ) {
    return value.detail.slice(0, 240);
  }

  return null;
}

export class ReviewApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ReviewApiError";
    this.status = status;
  }

  static async fromResponse(response: Response): Promise<ReviewApiError> {
    let detail: string | null = null;

    try {
      detail = safeErrorDetail(await response.json());
    } catch {
      // The HTTP status remains sufficient when an error body is not JSON.
    }

    return new ReviewApiError(
      response.status,
      detail ?? `The local review service returned HTTP ${response.status}.`,
    );
  }
}

export function readableClientError(error: unknown): string {
  if (error instanceof InvalidLaunchTokenError) {
    return error.message;
  }

  if (error instanceof ReviewApiError) {
    return error.message;
  }

  if (error instanceof TypeError) {
    return "The local review service could not be reached.";
  }

  return "The review operation could not be completed.";
}

async function expectOk(response: Response): Promise<Response> {
  if (!response.ok) {
    throw await ReviewApiError.fromResponse(response);
  }

  return response;
}

export async function checkReviewApiHealth(): Promise<HealthResponse> {
  const response = await expectOk(
    await fetch(`${API_PREFIX}/health`, {
      cache: "no-store",
      credentials: "same-origin",
      headers: { Accept: "application/json" },
    }),
  );

  return (await response.json()) as HealthResponse;
}

export class ReviewApiClient {
  readonly #token: string;

  constructor(token: string) {
    if (!isValidLaunchToken(token)) {
      throw new InvalidLaunchTokenError();
    }

    this.#token = token;
  }

  async checkAuthentication(): Promise<void> {
    await expectOk(
      await fetch(`${API_PREFIX}/auth-check`, {
        cache: "no-store",
        credentials: "same-origin",
        headers: {
          Accept: "application/json",
          [API_TOKEN_HEADER]: this.#token,
        },
      }),
    );
  }

  async #requestJson<T>(
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    headers.set(API_TOKEN_HEADER, this.#token);

    const response = await expectOk(
      await fetch(`${API_PREFIX}${path}`, {
        ...init,
        cache: "no-store",
        credentials: "same-origin",
        headers,
      }),
    );

    return (await response.json()) as T;
  }

  async #requestBlob(path: string): Promise<Response> {
    return expectOk(
      await fetch(`${API_PREFIX}${path}`, {
        cache: "no-store",
        credentials: "same-origin",
        headers: {
          Accept: "image/png,image/jpeg,application/pdf",
          [API_TOKEN_HEADER]: this.#token,
        },
      }),
    );
  }

  createSession(file: File): Promise<ReviewSession> {
    const mediaType =
      file.type || (file.name.toLowerCase().endsWith(".pdf") ? "application/pdf" : "");
    return this.#requestJson<ReviewSession>("/review-sessions", {
      method: "POST",
      headers: { "Content-Type": mediaType },
      body: file,
    });
  }

  getSession(sessionId: string): Promise<ReviewSession> {
    return this.#requestJson<ReviewSession>(
      `/review-sessions/${encodeURIComponent(sessionId)}`,
    );
  }

  analyzeSession(
    sessionId: string,
    settings: ImageSettings,
  ): Promise<ReviewSession> {
    return this.#requestJson<ReviewSession>(
      `/review-sessions/${encodeURIComponent(sessionId)}/analysis`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      },
    );
  }

  revisePlan(
    sessionId: string,
    request: RevisePlanRequest,
  ): Promise<ReviewSession> {
    return this.#requestJson<ReviewSession>(
      `/review-sessions/${encodeURIComponent(sessionId)}/plan`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
      },
    );
  }

  exportSession(
    sessionId: string,
    revisions: PageRevision[],
  ): Promise<ReviewSession> {
    return this.#requestJson<ReviewSession>(
      `/review-sessions/${encodeURIComponent(sessionId)}/export`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revisions: revisions }),
      },
    );
  }

  async getSource(sessionId: string): Promise<Blob> {
    const response = await this.#requestBlob(
      `/review-sessions/${encodeURIComponent(sessionId)}/source`,
    );
    return response.blob();
  }

  async getPageSource(sessionId: string, pageNumber: number): Promise<Blob> {
    const response = await this.#requestBlob(
      `/review-sessions/${encodeURIComponent(sessionId)}/pages/${pageNumber}/source`,
    );
    return response.blob();
  }

  async getExport(
    sessionId: string,
  ): Promise<{ blob: Blob; status: ReviewedOutputStatus | null }> {
    const response = await this.#requestBlob(
      `/review-sessions/${encodeURIComponent(sessionId)}/export`,
    );
    const status = response.headers.get("X-BIDR-Verification-Status");

    return {
      blob: await response.blob(),
      status:
        status === "passed" ||
        status === "verified_with_human_overrides" ||
        status === "review_required"
          ? status
          : null,
    };
  }

  async deleteSession(sessionId: string, keepalive = false): Promise<void> {
    await expectOk(
      await fetch(
        `${API_PREFIX}/review-sessions/${encodeURIComponent(sessionId)}`,
        {
          method: "DELETE",
          cache: "no-store",
          credentials: "same-origin",
          keepalive,
          headers: { [API_TOKEN_HEADER]: this.#token },
        },
      ),
    );
  }
}
