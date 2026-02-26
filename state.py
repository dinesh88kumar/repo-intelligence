from typing import TypedDict, List


class AgentState(TypedDict):
    repo_path: str
    repo_tree: str
    key_files: str
    tech_stack: str
    business_summary: str
    evidence: List[str]
    final_report: str
