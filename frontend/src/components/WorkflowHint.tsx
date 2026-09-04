import { useState } from "react";

const STORAGE_KEY = "pr-warden-workflow-hint-dismissed";

export function WorkflowHint() {
  const [dismissed, setDismissed] = useState<boolean>(
    () => localStorage.getItem(STORAGE_KEY) === "true",
  );

  if (dismissed) {
    return null;
  }

  function dismiss() {
    localStorage.setItem(STORAGE_KEY, "true");
    setDismissed(true);
  }

  return (
    <div className="hint-banner">
      <span>Step 1: Ingest a repo &rarr; Step 2: Review a PR &rarr; Step 3: View history</span>
      <button
        type="button"
        className="hint-banner-dismiss"
        onClick={dismiss}
        aria-label="Dismiss"
      >
        &times;
      </button>
    </div>
  );
}
