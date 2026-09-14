/**
 * The dot-plus-muted-text treatment used for every status indicator except the one hero
 * verdict pill per view. "sec"/"qua"/"tst" are fixed agent-identity colours (used in the tab
 * list and finding rails, so a colour always means the same agent). "approve"/"comment"/
 * "request-changes" are verdict-severity colours (used wherever a specific verdict is being
 * reported, e.g. a per-agent panel head or a history row). "ok" is the neutral/positive tone
 * for meta tags like "incremental" or "cached".
 */
export type DotColor = "sec" | "qua" | "tst" | "ok" | "approve" | "request-changes" | "comment";

export function StatusTag({ color, label }: { color: DotColor; label: string }) {
  return (
    <span className="tag">
      <span className={`dot dot-${color}`} />
      {label}
    </span>
  );
}
