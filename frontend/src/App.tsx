import { useState } from "react";
import { ApiKeyBar } from "./components/ApiKeyBar";
import { HistoryList } from "./components/HistoryList";
import { IngestForm } from "./components/IngestForm";
import { OpenPrsList } from "./components/OpenPrsList";
import { ReviewForm } from "./components/ReviewForm";
import { Sidebar, type Section } from "./components/Sidebar";
import { WorkflowHint } from "./components/WorkflowHint";
import { useApiKey } from "./hooks/useApiKey";

const TITLES: Record<Section, string> = {
  ingest: "Ingest a repository",
  review: "Review a pull request",
  history: "Review history",
  prs: "Open pull requests",
};

const DESCRIPTIONS: Record<Section, string> = {
  ingest:
    "Index a GitHub repo's issues, commits, and merged PRs so pr-warden has context for reviews. Run this once per repo, then use Review to analyse a pull request.",
  review:
    "Run pr-warden's agents against a pull request to get a security, quality, and test review with a final verdict.",
  history: "See past reviews pr-warden has run, with their verdicts and summaries.",
  prs: "Browse a repo's open pull requests and jump straight into reviewing one.",
};

function App() {
  const [section, setSection] = useState<Section>("review");
  const [apiKey, setApiKey] = useApiKey();

  return (
    <div className="app-layout">
      <Sidebar active={section} onSelect={setSection} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <ApiKeyBar apiKey={apiKey} onChange={setApiKey} />
        {!apiKey && (
          <div className="warning-banner">
            Enter your API key above to get started. It's stored only in your browser and sent
            only to this app's backend.
          </div>
        )}
        <WorkflowHint />
        <div className="main-content">
          <h1>{TITLES[section]}</h1>
          <p className="page-description">{DESCRIPTIONS[section]}</p>
          {section === "ingest" && <IngestForm apiKey={apiKey} />}
          {section === "review" && <ReviewForm apiKey={apiKey} />}
          {section === "history" && <HistoryList apiKey={apiKey} />}
          {section === "prs" && <OpenPrsList apiKey={apiKey} />}
        </div>
      </div>
    </div>
  );
}

export default App;
