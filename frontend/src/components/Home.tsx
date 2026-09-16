import { GitPullRequest } from "lucide-react";
import { featuredReview, featuredReviewIndexed, featuredReviewRepo } from "../data/featured-review";
import { AgentTabs } from "./AgentTabs";
import { VerdictCard } from "./VerdictCard";

const AGENT_COUNT = 3;

export function Home({ onNavigate }: { onNavigate: (hash: string) => void }) {
  return (
    <div className="regions">
      <section className="hero">
        <span className="eyebrow">Multi-agent code review</span>
        <h1>Review that can't invent findings.</h1>
        <p className="lede">
          Every issue an agent reports must quote the diff word for word. A plain string check
          confirms the quote is really there, and drops the ones that aren't. No second model
          grading the first.{" "}
          <a href="https://github.com/Amowixcode/pr-warden" target="_blank" rel="noreferrer">
            See the code on GitHub
          </a>
        </p>
      </section>

      <section>
        <div className="sec-head">
          <h2>A real review, start to finish.</h2>
          <p>Run against an open pull request in {featuredReviewRepo}. Nothing here is generated for the page.</p>
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
          showMoreToggle
        />
      </section>

      <section>
        <div className="sec-head">
          <h2>Three things most review bots don't do.</h2>
        </div>
        <div className="cols">
          <div className="col">
            <h3>Findings are verified, not trusted</h3>
            <p>
              Each agent must return the exact diff lines its finding rests on. Python checks the
              quote against the diff and discards anything it can't locate. Hallucinated findings
              never reach you.
            </p>
          </div>
          <div className="col">
            <h3>The verdict is deterministic</h3>
            <p>
              No fourth model decides. A fixed rule merges the three agents, and a non-empty issue
              list can never carry an approval, even when every agent said approve.
            </p>
          </div>
          <div className="col">
            <h3>It knows the repository</h3>
            <p>
              Issues, commits and merged pull requests are indexed first, so a review can draw on
              what the project already discussed rather than reading the diff in isolation.
            </p>
          </div>
        </div>
      </section>

      <section>
        <div className="sec-head">
          <h2>Context the review actually used.</h2>
          <p>Retrieved from the repository's own history at review time, not counted live.</p>
        </div>
        <div className="strip">
          <span className="strip-lead">Indexed for this repository</span>
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
      </section>

      <section>
        <div className="sec-head">
          <h2>What each agent found.</h2>
          <p>Three narrow prompts, run in parallel. They reach their own conclusions.</p>
        </div>
        <AgentTabs
          results={{
            security: featuredReview.security_result,
            quality: featuredReview.quality_result,
            test: featuredReview.test_result,
          }}
        />
      </section>

      <section>
        <div className="sec-head">
          <h2>How it works.</h2>
        </div>
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
      </section>

      <section className="secondary">
        <button type="button" className="btn" onClick={() => onNavigate("#/review")}>
          <GitPullRequest size={14} />
          Review a pull request
        </button>
        <button type="button" className="btn ghost" onClick={() => onNavigate("#/history")}>
          Browse all reviews
        </button>
      </section>
    </div>
  );
}
