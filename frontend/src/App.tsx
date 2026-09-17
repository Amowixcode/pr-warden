import { Home } from "./components/Home";
import { HistoryList } from "./components/HistoryList";
import { IngestForm } from "./components/IngestForm";
import { OpenPrsList } from "./components/OpenPrsList";
import { ReviewDetail } from "./components/ReviewDetail";
import { ReviewForm } from "./components/ReviewForm";
import { Sidebar, type Section } from "./components/Sidebar";
import { WorkflowHint } from "./components/WorkflowHint";
import { useHashRoute } from "./hooks/useHashRoute";
import { useTheme } from "./hooks/useTheme";

const TITLES: Record<Exclude<Section, "home">, string> = {
  review: "Review a pull request",
  history: "Review history",
  prs: "Open pull requests",
  ingest: "Ingest a repo",
};

const DESCRIPTIONS: Record<Exclude<Section, "home">, string> = {
  review:
    "Run pr-warden's agents against a pull request to get a security, quality, and test review with a final verdict.",
  history: "See past reviews pr-warden has run, with their verdicts and summaries.",
  prs: "Browse a repo's open pull requests and jump straight into reviewing one.",
  ingest:
    "Index a repository's issues, commits, and merged PRs into the vector store so reviews have historical context.",
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
        <WorkflowHint />
        <div className={route.view === "home" ? "main-content home" : "main-content"}>
          {route.view === "home" && <Home onNavigate={navigate} />}

          {route.view === "review-detail" && <ReviewDetail id={route.id} />}

          {route.view === "review-form" && (
            <>
              <h1>{TITLES.review}</h1>
              <p className="page-description">{DESCRIPTIONS.review}</p>
              <ReviewForm
                key={`${route.prefillRepo ?? ""}-${route.prefillPr ?? ""}`}
                prefillRepo={route.prefillRepo}
                prefillPr={route.prefillPr}
                jobId={route.jobId}
                onNavigate={navigate}
              />
            </>
          )}

          {route.view === "section" && (
            <>
              <h1>{TITLES[route.section]}</h1>
              <p className="page-description">{DESCRIPTIONS[route.section]}</p>
              {route.section === "history" && <HistoryList />}
              {route.section === "prs" && (
                <OpenPrsList
                  onReview={(repo, pr) =>
                    navigate(`#/review?repo=${encodeURIComponent(repo)}&pr=${pr}`)
                  }
                />
              )}
              {route.section === "ingest" && (
                <IngestForm jobId={route.jobId} onNavigate={navigate} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
