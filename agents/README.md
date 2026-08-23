# agents/ — review graph design

The multi-agent PR review pipeline described in the top-level `CLAUDE.md`/`README.md` ("runs
parallel agents (security, quality, test) backed by OpenAI"). Fully implemented and wired into
`core/review_service.py::review_pr` — see "Integration point" below.

## Graph shape

```
              ┌─────────────────┐
        ┌────▶│  security_agent │────┐
        │     └─────────────────┘    │
┌───────┴───┐  ┌─────────────────┐   ▼   ┌─────────────┐      ┌─────┐
│   START   │─▶│  quality_agent  │──────▶│ summarizer  │─────▶│ END │
└───────┬───┘  └─────────────────┘   ▲   └─────────────┘      └─────┘
        │     ┌─────────────────┐    │
        └────▶│   test_agent    │────┘
              └─────────────────┘
```

`START` has an edge to each of the three agent nodes — LangGraph runs nodes with no dependency
between them concurrently in the same superstep, so all three fire in parallel (fan-out). Each
agent node has an edge into `summarizer`, which only executes once all three have completed
(fan-in). `summarizer` has an edge to `END`.

## Node responsibilities

- **`security_agent` / `quality_agent` / `test_agent`** (`agents/security_agent.py`,
  `agents/quality_agent.py`, `agents/test_agent.py`): each reads `state["pr"]` (the `PRData` —
  diff, title, body, changed files) and `state["context"]` (the `PRContext` — retrieved similar
  issues/merged PRs/commits from RAG), calls OpenAI with its own specialist prompt, and returns a
  **partial state update** containing only its own key: `{"security_result": AgentResult(...)}`,
  `{"quality_result": AgentResult(...)}`, or `{"test_result": AgentResult(...)}` respectively.
  Each agent must never write to a key other than its own.
- **`summarizer`** (`agents/summarizer.py`): runs only after all three agents complete, so
  `state["security_result"]`, `state["quality_result"]`, and `state["test_result"]` are
  guaranteed populated. Reads all three, applies the merge policy below, and returns
  `{"final_verdict": AgentResult(...)}`. Deterministic — no OpenAI call.

## Merge policy contract

`agents/summarizer.py::summarizer` implements this rule:

- `verdict` = `"REQUEST_CHANGES"` if **any** agent's verdict is `"REQUEST_CHANGES"`
- else `"COMMENT"` if **any** agent's verdict is `"COMMENT"`
- else `"APPROVE"` (only when all three agents approved)
- `issues` = all three agents' `issues` lists combined, capped to the first 5 total
- `suggestions` = all three agents' `suggestions` lists combined, capped to the first 3 total
- `summary` = a synthesized one-liner (e.g. `"REQUEST_CHANGES — 2 issues flagged by security,
  test coverage."`, or `"No blocking concerns from security, quality, or test coverage review."`
  when APPROVE) — never each agent's own summary text repeated. Still a formula, not an LLM call
  (an earlier draft of this doc assumed the summarizer would synthesize a new summary via OpenAI;
  the first implemented version was a pure unbounded concatenation instead; this later revision
  replaced that concatenation with the capped, synthesized one-liner described above — still no
  OpenAI call, per a deliberate cost/latency tradeoff).

## Why no LangGraph reducer is needed

Each parallel agent writes to its **own** dedicated state key (`security_result`,
`quality_result`, `test_result`) rather than all three writing into one shared field. This means
there is no concurrent-write conflict for LangGraph to resolve, so no `Annotated[X, reducer_fn]`
is needed anywhere in `ReviewState`. The tempting alternative — one shared `results: dict` or
`results: list` field that every agent appends to — would require a reducer (e.g.
`Annotated[list, operator.add]`) to merge concurrent partial updates safely, and is unnecessary
complexity for a fixed set of three known agents. Don't "simplify" the schema into that shape
without adding the reducer, or the graph will raise `InvalidUpdateError` the first time two
agents complete in the same superstep.

## Integration point

`core/review_service.py::review_pr` builds the initial `ReviewState` from the `PRData`/
`PRContext` it already fetches, invokes the compiled graph (`agents/graph.py`'s `graph.ainvoke`),
and maps `final_verdict` into `ReviewResult` — same field shapes, no translation logic needed.
`review_pr`'s public signature and `ReviewResult` are unchanged from the earlier single-prompt
implementation, so `cli/main.py` required no changes.

## Graph wiring

`agents/graph.py::build_graph()` compiles the `StateGraph` described above: `add_node` for all
four nodes, `add_edge(START, agent)` for each of the three specialist agents (fan-out), and a
single `add_edge([security_agent, quality_agent, test_agent], "summarizer")` call for fan-in —
the list form registers a joint "wait for all three" trigger. For this specific topology (all
three agents are direct children of `START`, so they always complete in the same superstep),
three separate `add_edge` calls happen to produce the same single-execution behavior in practice
(verified empirically) — but the list form is used because it's self-documenting and is the form
that stays correct if the topology later changes (e.g. a retry/conditional edge on one agent).

`build_graph()` is exposed separately from the module-level `graph` singleton specifically so
tests can rebuild the graph after patching the node functions (patches only take effect on a
graph built after the patch, since `.compile()` bakes in whatever function references are
current at build time) — see `tests/unit/test_graph.py`.
