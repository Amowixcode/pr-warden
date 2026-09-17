export type Verdict = "APPROVE" | "REQUEST_CHANGES" | "COMMENT";

export interface AgentResult {
  summary: string;
  verdict: Verdict;
  issues: string[];
  suggestions: string[];
}

export interface ReviewResponse {
  pr_number: number;
  summary: string;
  verdict: Verdict;
  issues: string[];
  suggestions: string[];
  security_result: AgentResult;
  quality_result: AgentResult;
  test_result: AgentResult;
  incremental: boolean;
  cached: boolean;
  prior_verdict: Verdict | null;
  prior_head_sha: string | null;
}

export interface ReviewHistoryItem {
  id: number;
  repo: string;
  pr_number: number;
  head_sha: string;
  verdict: Verdict;
  summary: string;
  issues: string[];
  suggestions: string[];
  created_at: string;
}

export interface ReviewDetail {
  id: number;
  repo: string;
  pr_number: number;
  head_sha: string;
  verdict: Verdict;
  summary: string;
  issues: string[];
  suggestions: string[];
  security_result: AgentResult | null;
  quality_result: AgentResult | null;
  test_result: AgentResult | null;
  created_at: string;
}

export interface IngestResponse {
  issues_indexed: number;
  prs_indexed: number;
  commits_indexed: number;
  total_newly_indexed: number;
  incremental: boolean;
}

export interface OpenPRResponse {
  number: number;
  title: string;
  author: string;
  age_days: number;
}

export type JobStatus = "running" | "succeeded" | "failed";

export interface Job {
  id: string;
  kind: "review" | "ingest";
  status: JobStatus;
  stage: string;
  result: ReviewResponse | IngestResponse | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

