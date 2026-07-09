# agents/ — review graph design

Contract for the multi-agent PR review pipeline described in the top-level `CLAUDE.md`/`README.md`
("runs parallel agents (security, quality, test) backed by OpenAI"). This document plus
`state.py` are the contract; no node logic is implemented yet — see "Out of scope" below.

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
- `issues` = concatenation of all three agents' `issues` lists
- `suggestions` = concatenation of all three agents' `suggestions` lists
- `summary` = each agent's own summary, labeled by category and joined — a formula, not an LLM
  call (an earlier draft of this doc assumed the summarizer would synthesize a new summary via
  OpenAI; the implemented ticket's scope was a pure deterministic merge instead).

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

## Integration point (out of scope here)

Eventually `core/review_service.py` will build the initial `ReviewState` from a `PRData`/
`PRContext` it already fetches, invoke the compiled graph, and map `final_verdict` into (or
replace) today's single-prompt `ReviewResult`. Not implemented as part of this contract — a
later graph-wiring ticket's job.

## Out of scope (future tickets)

The compiled `StateGraph` wiring itself (fan-out from `START`, fan-in into `summarizer`, edge to
`END`) and integration into `core/review_service.py`/the CLI — not implemented yet. The four
nodes (`security_agent.py`, `quality_agent.py`, `test_agent.py`, `summarizer.py`) all exist and
are independently unit-tested, but nothing yet invokes them as a graph.
