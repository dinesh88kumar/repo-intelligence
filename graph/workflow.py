from langgraph.graph import StateGraph, END
from state import AgentState
from agents.repo_scanner import repo_scanner_agent
from agents.business_context import business_context_agent
from agents.report_generator import report_generator_agent


def build_graph(llm):
    graph = StateGraph(AgentState)

    graph.add_node("scan_repo", lambda s: repo_scanner_agent(llm, s))
    graph.add_node("business_context", lambda s: business_context_agent(llm, s))
    graph.add_node("report", report_generator_agent)

    graph.set_entry_point("scan_repo")

    graph.add_edge("scan_repo", "business_context")
    graph.add_edge("business_context", "report")
    graph.add_edge("report", END)

    return graph.compile()
