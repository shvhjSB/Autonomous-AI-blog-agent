"""
LangGraph state-graph pipeline — wires all agent nodes together.

Graph topology:
    START → router ──┬── researcher → planner ──┐
                     └─────────────→ planner    │
                                                ↓
                                        fanout → writer (×N parallel)
                                                ↓
                                     reducer subgraph:
                                       merge_sections
                                           ↓
                                       plan_images
                                           ↓
                                     generate_and_export
                                                ↓
                                        seo_optimizer → END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from blog_agent.agents.compiler import (
    generate_and_export,
    merge_sections,
    plan_images,
)
from blog_agent.agents.planner import fanout_to_writers, planner_node
from blog_agent.agents.researcher import researcher_node
from blog_agent.agents.router import route_after_router, router_node
from blog_agent.agents.seo_optimizer import seo_optimizer_node
from blog_agent.agents.writer import writer_node
from blog_agent.schemas import BlogState


def build_graph():
    """Construct and compile the full blog-writing LangGraph pipeline.

    Returns a compiled ``CompiledStateGraph`` ready to be invoked with
    an initial ``BlogState`` dict.
    """

    # ------------------------------------------------------------------
    # Reducer subgraph (post-writing assembly)
    # ------------------------------------------------------------------
    reducer = StateGraph(BlogState)
    reducer.add_node("merge_sections", merge_sections)
    reducer.add_node("plan_images", plan_images)
    reducer.add_node("generate_and_export", generate_and_export)

    reducer.add_edge(START, "merge_sections")
    reducer.add_edge("merge_sections", "plan_images")
    reducer.add_edge("plan_images", "generate_and_export")
    reducer.add_edge("generate_and_export", END)

    reducer_subgraph = reducer.compile()

    # ------------------------------------------------------------------
    # Main graph
    # ------------------------------------------------------------------
    graph = StateGraph(BlogState)

    graph.add_node("router", router_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("planner", planner_node)
    graph.add_node("writer", writer_node)
    graph.add_node("compiler", reducer_subgraph)
    graph.add_node("seo_optimizer", seo_optimizer_node)

    # Edges
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {"researcher": "researcher", "planner": "planner"},
    )
    graph.add_edge("researcher", "planner")
    graph.add_conditional_edges("planner", fanout_to_writers, ["writer"])
    graph.add_edge("writer", "compiler")
    graph.add_edge("compiler", "seo_optimizer")
    graph.add_edge("seo_optimizer", END)

    return graph.compile()
