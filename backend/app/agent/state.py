from typing import TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    is_in_scope: Optional[bool]
    schema_context: Optional[str]
    sql_query: Optional[str]
    is_valid_sql: Optional[bool]
    sql_errors: Optional[str]
    optimized_sql: Optional[str]
    query_results: Optional[str]
    explanation: Optional[str]
    sql_generation_attempts: int
    execution_time_ms: Optional[float]
