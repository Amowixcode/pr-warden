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

export interface OpenPRResponse {
  number: number;
  title: string;
  author: string;
  age_days: number;
}

export interface IngestResponse {
  issues_indexed: number;
  prs_indexed: number;
  commits_indexed: number;
  total_newly_indexed: number;
  incremental: boolean;
}
