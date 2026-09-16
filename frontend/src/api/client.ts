import type {
  IngestResponse,
  OpenPRResponse,
  ReviewDetail,
  ReviewHistoryItem,
  ReviewResponse,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

// An operator-configured value baked into the build, not something a visitor enters — see
// DEPLOY.md's note that this is not a security boundary (it's visible in the network tab of
// any browser running this bundle). It only deters opportunistic scanners; real protection
// for /review is the server-side repo allowlist.
const API_KEY = import.meta.env.VITE_API_KEY ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (API_KEY) {
    headers.set("X-API-Key", API_KEY);
  }

  const response = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText || `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") {
        detail = body.detail;
      }
    } catch {
      // Non-JSON error body — keep the fallback message.
    }
    throw new ApiError(response.status, detail);
  }

  return (await response.json()) as T;
}

export function reviewPr(
  repo: string,
  prNumber: number,
  full = false,
): Promise<ReviewResponse> {
  return request<ReviewResponse>("/review", {
    method: "POST",
    body: JSON.stringify({ repo, pr_number: prNumber, full }),
  });
}

export function ingestRepository(repo: string): Promise<IngestResponse> {
  return request<IngestResponse>("/ingest", {
    method: "POST",
    body: JSON.stringify({ repo }),
  });
}

export function listOpenPrs(owner: string, repo: string): Promise<OpenPRResponse[]> {
  return request<OpenPRResponse[]>(
    `/prs/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`,
    { method: "GET" },
  );
}

export function getReviewHistory(): Promise<ReviewHistoryItem[]> {
  return request<ReviewHistoryItem[]>("/reviews", { method: "GET" });
}

/** GET /health — used to tell "server is cold" from "request in flight". */
export function getHealth(): Promise<{ status: string }> {
  return request<{ status: string }>("/health", { method: "GET" });
}

/** GET /reviews/{id} — a single full review, including per-agent detail. */
export function getReviewDetail(id: number): Promise<ReviewDetail> {
  return request<ReviewDetail>(`/reviews/${id}`, { method: "GET" });
}
