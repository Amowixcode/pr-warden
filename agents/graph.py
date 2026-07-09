from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.quality_agent import quality_agent
from agents.security_agent import security_agent
from agents.state import ReviewState
from agents.summarizer import summarizer
from agents.test_agent import test_agent


def build_graph() -> CompiledStateGraph:
    """Build and compile the security/quality/test -> summarizer review graph.

    Graph shape (see agents/README.md): START fans out to all three specialist agents in
    parallel. Fan-in into summarizer uses a single add_edge call with a *list* of all three
    start nodes — LangGraph's documented "wait for ALL of the start nodes to complete" join.
    For this specific topology (all three agents are direct children of START, so they always
    complete in the same superstep), three separate add_edge calls happen to behave the same
    way in practice — LangGraph schedules each distinct target once per superstep regardless of
    how many of its incoming edges fired. The list form is used anyway because it's the
    semantically correct, self-documenting way to declare "depends on all three", and it's the
    form that stays correct if the topology later changes (e.g. a retry/conditional edge on one
    agent that could make it finish in a later superstep than the other two).
    """
    builder = StateGraph(ReviewState)

    builder.add_node("security_agent", security_agent)
    builder.add_node("quality_agent", quality_agent)
    builder.add_node("test_agent", test_agent)
    builder.add_node("summarizer", summarizer)

    builder.add_edge(START, "security_agent")
    builder.add_edge(START, "quality_agent")
    builder.add_edge(START, "test_agent")

    builder.add_edge(["security_agent", "quality_agent", "test_agent"], "summarizer")
    builder.add_edge("summarizer", END)

    return builder.compile()


graph: CompiledStateGraph = build_graph()
