from langgraph.graph import StateGraph, END
from app.agent.state import AgentState
from app.agent.nodes.nodes import AgentNodes

def create_agent_graph():
    nodes = AgentNodes()
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("detect_intent", nodes.detect_intent)
    workflow.add_node("reject_out_of_scope", nodes.reject_out_of_scope)
    workflow.add_node("retrieve_schema", nodes.retrieve_schema)
    workflow.add_node("generate_sql", nodes.generate_sql)
    workflow.add_node("validate_sql", nodes.validate_sql)
    workflow.add_node("optimize_sql", nodes.optimize_sql)
    workflow.add_node("execute_query", nodes.execute_query)
    workflow.add_node("generate_explanation", nodes.generate_explanation)
    workflow.add_node("format_response", nodes.format_response)

    # Entry point
    workflow.set_entry_point("detect_intent")

    # Edges and conditional routing
    def check_scope(state: AgentState):
        return "in_scope" if state.get("is_in_scope") else "out_of_scope"

    workflow.add_conditional_edges(
        "detect_intent",
        check_scope,
        {
            "in_scope": "retrieve_schema",
            "out_of_scope": "reject_out_of_scope"
        }
    )

    workflow.add_edge("reject_out_of_scope", END)
    workflow.add_edge("retrieve_schema", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")

    def check_validity(state: AgentState):
        if state.get("is_valid_sql"):
            return "valid"
        if state.get("sql_generation_attempts", 0) >= 3:
            return "invalid_max_retries"
        return "invalid"

    workflow.add_conditional_edges(
        "validate_sql",
        check_validity,
        {
            "valid": "optimize_sql",
            "invalid": "generate_sql",
            "invalid_max_retries": "format_response" 
        }
    )

    workflow.add_edge("optimize_sql", "execute_query")
    workflow.add_edge("execute_query", "generate_explanation")
    workflow.add_edge("generate_explanation", "format_response")
    workflow.add_edge("format_response", END)

    return workflow.compile()

# Provide a ready-to-use compiled graph
agent_app = create_agent_graph()
