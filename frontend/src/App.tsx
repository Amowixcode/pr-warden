import { ApiKeyBar } from "./components/ApiKeyBar";
import { Home } from "./components/Home";
import { HistoryList } from "./components/HistoryList";
import { IngestForm } from "./components/IngestForm";
import { OpenPrsList } from "./components/OpenPrsList";
import { ReviewDetail } from "./components/ReviewDetail";
import { ReviewForm } from "./components/ReviewForm";
import { Sidebar, type Section } from "./components/Sidebar";
import { WorkflowHint } from "./components/WorkflowHint";
import { useApiKey } from "./hooks/useApiKey";
import { useHashRoute } from "./hooks/useHashRoute";
import { useTheme } from "./hooks/useTheme";

const TITLES: Record<Exclude<Section, "home">, string> = {
  ingest: "Ingest a repository",
  review: "Review a pull request",
  history: "Review history",
  prs: "Open pull requests",
};

const DESCRIPTIONS: Record<Exclude<Section, "home">, string> = {
  ingest:
    "Index a GitHub repo's issues, commits, and merged PRs so pr-warden has context for reviews. Run this once per repo, then use Review to analyse a pull request.",
  review:
    "Run pr-warden's agents against a pull request to get a security, quality, and test review with a final verdict.",
  history: "See past reviews pr-warden has run, with their verdicts and summaries.",
  prs: "Browse a repo's open pull requests and jump straight into reviewing one.",
};

function activeSection(route: ReturnType<typeof useHashRoute>["route"]): Section | null {
  switch (route.view) {
    case "home":
      return "home";
    case "section":
      return route.section;
    case "review-form":
    case "review-detail":
      return "review";
  }
}

function App() {
  const { route, navigate } = useHashRoute();
  const [apiKey, setApiKey] = useApiKey();
  const { theme, toggle } = useTheme();

  return (
    <div className="app-layout">
      <Sidebar
        active={activeSection(route)}
        onSelect={(section) => navigate(section === "home" ? "#/" : `#/${section}`)}
        theme={theme}
        onToggleTheme={toggle}
      />
      <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
        <ApiKeyBar apiKey={apiKey} onChange={setApiKey} />
        {!apiKey && route.view !== "home" && (
          <div className="warning-banner">
            Enter your API key above to get started. It's stored only in your browser and sent
            only to this app's backend.
          </div>
        )}
        <WorkflowHint />
        <div className="main-content">
          {route.view === "home" && <Home onNavigate={navigate} />}

          {route.view === "review-detail" && <ReviewDetail id={route.id} apiKey={apiKey} />}

          {route.view === "review-form" && (
            <>
              <h1>{TITLES.review}</h1>
              <p className="page-description">{DESCRIPTIONS.review}</p>
              <ReviewForm
                key={`${route.prefillRepo ?? ""}-${route.prefillPr ?? ""}`}
                apiKey={apiKey}
                prefillRepo={route.prefillRepo}
                prefillPr={route.prefillPr}
              />
            </>
          )}

          {route.view === "section" && (
            <>
              <h1>{TITLES[route.section]}</h1>
              <p className="page-description">{DESCRIPTIONS[route.section]}</p>
              {route.section === "ingest" && <IngestForm apiKey={apiKey} />}
              {route.section === "history" && <HistoryList apiKey={apiKey} />}
              {route.section === "prs" && (
                <OpenPrsList
                  apiKey={apiKey}
                  onReview={(repo, pr) =>
                    navigate(`#/review?repo=${encodeURIComponent(repo)}&pr=${pr}`)
                  }
                />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
