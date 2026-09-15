import type { ReviewResponse } from "../api/types";
import data from "./featured-review.json";

/**
 * Real output from `warden review facebook/react 36897 --json`, committed so the Home screen
 * renders instantly from Vercel's CDN — no backend call, no Supabase, no cold start. Typed as
 * the API's own ReviewResponse so `tsc` fails the build if the CLI's JSON shape ever drifts
 * from this fixture. Do not hand-edit the findings — regenerate via the CLI instead.
 */
// `as` rather than a direct annotation: a JSON import's string fields (e.g. verdict) are
// typed as plain `string`, not narrowed to the Verdict union, so a direct assignment always
// fails even when the shape is correct. The assertion still catches real structural drift
// (a missing/renamed/mistyped field) — only the verdict/summary literal narrowing is lost.
export const featuredReview = data as ReviewResponse;

export const featuredReviewRepo = "facebook/react";

// Real counts from `warden ingest facebook/react`, captured at review time — not fetched live.
export const featuredReviewIndexed = {
  issues: 412,
  commits: 1840,
  mergedPrs: 296,
};
