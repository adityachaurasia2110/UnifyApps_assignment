from pydantic import BaseModel, Field
from typing import Optional

class IntentDetection(BaseModel):
    is_in_scope: bool = Field(description="True if the request is related to databases, SQL, employees, customers, or departments. False if it is general knowledge, sports, politics, etc.")

class SQLGeneration(BaseModel):
    sql_query: str = Field(description="The generated SQL query.")

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
