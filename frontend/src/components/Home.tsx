import { featuredReview, featuredReviewIndexed, featuredReviewRepo } from "../data/featured-review";
import { AgentTabs } from "./AgentTabs";
import { VerdictCard } from "./VerdictCard";

const AGENT_COUNT = 3;

export function Home({ onNavigate }: { onNavigate: (hash: string) => void }) {
  return (
    <div>
      <div className="intro">
        <h1>Context-aware pull request review</h1>
        <p>
          Indexes a repository's history into a vector store, then runs three agents in
          parallel against a pull request: security, code quality, and test coverage.{" "}
          <a href="https://github.com/Amowixcode/pr-warden" target="_blank" rel="noreferrer">
            See the code on GitHub
          </a>
        </p>
      </div>

      <VerdictCard
        repo={featuredReviewRepo}
        prNumber={featuredReview.pr_number}
        verdict={featuredReview.verdict}
        summary={featuredReview.summary}
        issues={featuredReview.issues}
        agentResults={{
          security: featuredReview.security_result,
          quality: featuredReview.quality_result,
          test: featuredReview.test_result,
        }}
        headMeta={`${AGENT_COUNT} agents`}
      />

      <div className="strip">
        <span className="strip-lead">Context retrieved for this review</span>
        <div className="stat">
          <b>{featuredReviewIndexed.issues.toLocaleString()}</b>
          <span>issues</span>
        </div>
        <div className="stat">
          <b>{featuredReviewIndexed.commits.toLocaleString()}</b>
          <span>commits</span>
        </div>
        <div className="stat">
          <b>{featuredReviewIndexed.mergedPrs.toLocaleString()}</b>
          <span>merged PRs</span>
        </div>
      </div>

      <h2 className="label">What each agent found</h2>
      <AgentTabs
        results={{
          security: featuredReview.security_result,
          quality: featuredReview.quality_result,
          test: featuredReview.test_result,
        }}
      />

      <h2 className="label">How it works</h2>
      <div className="flow">
        <div className="step">
          <div className="step-cmd">warden ingest</div>
          <div className="step-what">
            Issues, commits and merged PRs are embedded into a vector store. Once per repo.
          </div>
        </div>
        <div className="step">
          <div className="step-cmd">warden review</div>
          <div className="step-what">
            Relevant history is retrieved, then three agents assess the diff in parallel.
          </div>
        </div>
        <div className="step">
          <div className="step-cmd">→ verdict</div>
          <div className="step-what">
            Findings merge deterministically. Every finding must quote the diff verbatim.
          </div>
        </div>
      </div>

      <div className="secondary">
        <button type="button" className="btn" onClick={() => onNavigate("#/review")}>
          Review another PR
        </button>
        <button type="button" className="btn ghost" onClick={() => onNavigate("#/history")}>
          Browse all reviews
        </button>
        <p>No key needed to read results.</p>
      </div>
    </div>
  );
}
