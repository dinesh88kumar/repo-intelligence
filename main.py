from langchain_ollama.llms import OllamaLLM
from graph.workflow import build_graph

llm = OllamaLLM(model="qwen3:4b")

app = build_graph(llm)

initial_state = {
    "repo_path": "./sample_applications/shop_app",
    "repo_tree": "",
    "key_files": "",
    "tech_stack": "",
    "business_summary": "",
    "evidence": [],
    "final_report": "",
}

result = app.invoke(initial_state)

print(result["final_report"])
