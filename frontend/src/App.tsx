import { useState } from "react";
import { ApiKeyBar } from "./components/ApiKeyBar";
import { HistoryList } from "./components/HistoryList";
import { IngestForm } from "./components/IngestForm";
import { OpenPrsList } from "./components/OpenPrsList";
import { ReviewForm } from "./components/ReviewForm";
import { Sidebar, type Section } from "./components/Sidebar";
import { useApiKey } from "./hooks/useApiKey";

const TITLES: Record<Section, string> = {
  ingest: "Ingest a repository",
  review: "Review a pull request",
  history: "Review history",
  prs: "Open pull requests",
};

function App() {
  const [section, setSection] = useState<Section>("review");
  const [apiKey, setApiKey] = useApiKey();

  return (
    <div className="app-layout">
      <Sidebar active={section} onSelect={setSection} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <ApiKeyBar apiKey={apiKey} onChange={setApiKey} />
        <div className="main-content">
          <h1>{TITLES[section]}</h1>
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
