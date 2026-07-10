## Description
It is unclear whether `warden ingest` only fetches new issues/PRs/commits since the last ingestion of a given repo, or always re-fetches everything from scratch (bounded by the existing limit=100/200 defaults). For large, active repos, always refetching the full history on every `warden ingest` call is wasteful (GitHub API calls, OpenAI embedding calls, ChromaDB writes) and does not scale over repeated use.

## Scope
- Track the last-ingested timestamp (or cursor/ID) per repo
- On subsequent `warden ingest` calls for an already-ingested repo, only fetch issues/PRs/commits created/updated since the last ingestion
- Existing dedup-on-insert logic in ingestion/vector_store.py remains as a safety net
- Provide a `--full` flag to force a complete re-ingestion regardless of history

## Acceptance Criteria
- [ ] Last-ingested timestamp/cursor is persisted per repo
- [ ] Subsequent `warden ingest` calls only fetch new/updated items since the last ingestion, when available
- [ ] `--full` flag forces complete re-ingestion
- [ ] Unit tests covering: first ingest (no history, full fetch), second ingest (incremental), `--full` override
- [ ] Manual test: ingest a repo, then re-ingest after new activity, confirm only new items are fetched/embedded (reduced API calls)