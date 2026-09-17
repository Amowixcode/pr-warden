/**
 * A running background job's progress: the stage it's on, never a percentage — review has no
 * honest fraction to report (see core/review_service.py's on_stage contract).
 */
export function JobStageBanner({ stage }: { stage: string | null }) {
  return (
    <div className="loading-banner">
      <span className="spinner" />
      {stage ?? "Starting…"}
    </div>
  );
}
