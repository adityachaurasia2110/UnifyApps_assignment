import os, sys
sys.path.append(os.path.dirname(__file__))

from langchain_core.messages import HumanMessage
from app.agent.nodes.nodes import AgentNodes
from app.agent.state import AgentState

nodes = AgentNodes()
state = {"messages": [HumanMessage(content="Show all employees.")], "sql_generation_attempts": 0}

print("Running retrieve_schema...")
state.update(nodes.retrieve_schema(state))

for i in range(3):
    print(f"\n--- Iteration {i+1} ---")
    gen_result = nodes.generate_sql(state)
    state.update(gen_result)
    print("Generated SQL:", state.get("sql_query"))
    
    val_result = nodes.validate_sql(state)
    state.update(val_result)
    print("Is Valid SQL:", state.get("is_valid_sql"))
    print("Errors:", state.get("sql_errors"))
    
    if state.get("is_valid_sql"):
        print("Success!")
        break
