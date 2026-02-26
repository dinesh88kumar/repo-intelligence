from langchain_core.prompts import ChatPromptTemplate
from tools.repo_reader import scan_repository


def repo_scanner_agent(llm, state):
    tree, key_files, evidence = scan_repository(state["repo_path"])

    prompt = ChatPromptTemplate.from_template(
        """
        You are a senior software architect.

        Based on the repository structure and key files,
        identify the tech stack and frameworks used.

        Repo Tree:
        {tree}

        Key Files:
        {key_files}

        Return a concise tech stack summary.
        """
    )

    chain = prompt | llm
    tech_stack = chain.invoke(
        {
            "tree": tree,
            "key_files": key_files,
        }
    )

    return {
        "repo_tree": tree,
        "key_files": key_files,
        "tech_stack": tech_stack,
        "evidence": evidence,
    }
