import type { OpenPRResponse, ReviewHistoryItem, ReviewResponse } from "./types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit,
  apiKey: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (apiKey) {
    headers.set("X-API-Key", apiKey);
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
  apiKey: string,
): Promise<ReviewResponse> {
  return request<ReviewResponse>(
    "/review",
    { method: "POST", body: JSON.stringify({ repo, pr_number: prNumber }) },
    apiKey,
  );
}

export function listOpenPrs(
  owner: string,
  repo: string,
  apiKey: string,
): Promise<OpenPRResponse[]> {
  return request<OpenPRResponse[]>(
    `/prs/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}`,
    { method: "GET" },
    apiKey,
  );
}

export function getReviewHistory(apiKey: string): Promise<ReviewHistoryItem[]> {
  return request<ReviewHistoryItem[]>("/reviews", { method: "GET" }, apiKey);
}
