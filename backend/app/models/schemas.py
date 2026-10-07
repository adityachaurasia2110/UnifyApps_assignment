from pydantic import BaseModel, Field
from typing import Optional

class IntentDetection(BaseModel):
    is_in_scope: bool = Field(description="True if the request is related to databases, SQL, employees, customers, or departments. False if it is general knowledge, sports, politics, etc.")

class SQLGeneration(BaseModel):
    is_ambiguous: bool = Field(
        default=False, 
        description="True if the user's request is ambiguous, subjective, or missing required criteria (e.g. 'show the best employee', 'find good customers', or 'show records' without entity specified). False if the request is specific or has clear criteria."
    )
    clarification_question: Optional[str] = Field(
        default=None, 
        description="If is_ambiguous is True, provide a polite question asking the user to clarify specific options or criteria based on database schema columns."
    )
    sql_query: Optional[str] = Field(
        default="", 
        description="The generated SQL query if NOT ambiguous."
    )

class SQLOptimization(BaseModel):
    optimized_sql: str = Field(description="The optimized or formatted SQL query.")

class SQLExplanation(BaseModel):
    explanation: str = Field(description="Plain english explanation of the SQL query.")

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"

class ChatResponse(BaseModel):
    sql: Optional[str] = None
    explanation: Optional[str] = None
    results: Optional[str] = None
    error: Optional[str] = None
    clarification: Optional[str] = None
    execution_time_ms: Optional[float] = None
