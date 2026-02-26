from langchain_core.prompts import ChatPromptTemplate


def business_context_agent(llm, state):
    prompt = ChatPromptTemplate.from_template(
        """
        You are an expert product analyst.

        Based on the repository information below,
        infer the BUSINESS PURPOSE of the application.

        Tech Stack:
        {tech_stack}

        Key Files:
        {key_files}

        Provide:

        - What the application likely does
        - Target users
        - Main business workflows

        Be concise but insightful.
        """
    )

    chain = prompt | llm
    summary = chain.invoke(
        {
            "tech_stack": state["tech_stack"],
            "key_files": state["key_files"],
        }
    )

    return {"business_summary": summary}
