def report_generator_agent(state):
    report = f"""
# 🧠 Repository Intelligence Report

## 🔧 Tech Stack
{state['tech_stack']}

## 💼 Business Context
{state['business_summary']}

## 📂 Evidence Files
{chr(10).join(state['evidence'])}
"""

    return {"final_report": report}
