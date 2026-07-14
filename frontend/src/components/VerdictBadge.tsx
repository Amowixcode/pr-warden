import type { Verdict } from "../api/types";

const LABEL: Record<Verdict, string> = {
  APPROVE: "Approve",
  REQUEST_CHANGES: "Request changes",
  COMMENT: "Comment",
};

const CLASS: Record<Verdict, string> = {
  APPROVE: "approve",
  REQUEST_CHANGES: "request-changes",
  COMMENT: "comment",
};

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <span className={`pill ${CLASS[verdict]}`}>{LABEL[verdict]}</span>;
}
