## Description
Wire the LangGraph multi-agent graph and integrate it into the existing review flow, replacing the current single-prompt call.

## Scope
- `agents/graph.py`: builds and compiles a LangGraph StateGraph - fan-out to security/quality/test agents in parallel, fan-in to the summarizer
- `core/review_service.py`: replace `_call_openai`'s single-prompt flow with invoking the compiled graph, keeping the public function signature stable so `cli/` does not need to change (per CLAUDE.md's architecture principle - business logic stays in core/)

## Acceptance Criteria
- [ ] `agents/graph.py` compiles and runs the graph end-to-end
- [ ] `core/review_service.py` invokes the graph instead of a single prompt
- [ ] Public function signature/interface of `core/review_service.py` unchanged
- [ ] Tests proving the graph actually fans out to all three agents and fans back into the summarizer
- [ ] Depends on: security_agent, quality_agent, test_agent, summarizer issues