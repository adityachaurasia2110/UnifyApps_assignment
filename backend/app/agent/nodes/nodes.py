import json
import sqlglot
from langchain_core.messages import AIMessage, SystemMessage
from app.agent.state import AgentState
from app.models.schemas import IntentDetection, SQLGeneration, SQLExplanation
from app.services.llm_service import get_llm_service
from app.services.db_service import get_db_service

class AgentNodes:
    def __init__(self):
        self.llm_service = get_llm_service()
        self.db_service = get_db_service()

    def detect_intent(self, state: AgentState):
        messages = state.get("messages", [])
        if not messages:
            return {"is_in_scope": False}
        
        prompt = """Analyze the user's request and the conversation history. 
        Determine if the request is related to querying a database, SQL, or retrieving data about employees, departments, or customers.
        If it is about sports, politics, general knowledge, or creative writing, it is OUT OF SCOPE.
        """
        sys_msg = SystemMessage(content=prompt)
        result = self.llm_service.generate_structured_output([sys_msg] + messages, IntentDetection)
        return {"is_in_scope": result.is_in_scope}

    def reject_out_of_scope(self, state: AgentState):
        msg = AIMessage(content=json.dumps({
            "error": "I'm designed to assist only with SQL and database-related tasks. Please ask a question related to the provided database schema."
        }))
        return {"messages": [msg]}

    def retrieve_schema(self, state: AgentState):
        try:
            schema = self.db_service.get_schema()
            return {"schema_context": schema, "sql_generation_attempts": 0}
        except Exception as e:
            return {"schema_context": f"Error retrieving schema: {e}", "sql_generation_attempts": 0}

    def generate_sql(self, state: AgentState):
        schema = state.get("schema_context", "")
        messages = state.get("messages", [])
        errors = state.get("sql_errors", "")
        
        prompt = f"""You are an expert SQL assistant. Generate a SQL query for SQLite based on the user's request.
        Schema:
        {schema}
        
        Rules:
        1. Only use the provided tables/columns.
        2. Write standard read-only SQL.
        3. If there were previous errors with your SQL, fix them. Previous errors: {errors}
        """
        sys_msg = SystemMessage(content=prompt)
        result = self.llm_service.generate_structured_output([sys_msg] + messages, SQLGeneration)
        
        attempts = state.get("sql_generation_attempts", 0) + 1
        return {"sql_query": result.sql_query, "sql_generation_attempts": attempts}

    def validate_sql(self, state: AgentState):
        query = state.get("sql_query", "")
        try:
            parsed = sqlglot.parse(query)
            for statement in parsed:
                if not isinstance(statement, sqlglot.exp.Select):
                    return {"is_valid_sql": False, "sql_errors": f"Only SELECT (read-only) queries are allowed. Destructive operation detected: {query}"}
            return {"is_valid_sql": True, "sql_errors": None}
        except Exception as e:
            return {"is_valid_sql": False, "sql_errors": f"SQL syntax error: {str(e)}"}

    def optimize_sql(self, state: AgentState):
        query = state.get("sql_query", "")
        try:
            optimized = sqlglot.transpile(query, read="sqlite", write="sqlite", pretty=True)[0]
        except:
            optimized = query
        return {"optimized_sql": optimized}

    def execute_query(self, state: AgentState):
        query = state.get("optimized_sql", "") or state.get("sql_query", "")
        try:
            results = self.db_service.execute_query(query)
            # Serialize early to avoid huge states
            return {"query_results": json.dumps(results[:50])}
        except Exception as e:
            return {"query_results": f"Execution error: {e}"}

    def generate_explanation(self, state: AgentState):
        query = state.get("optimized_sql", "") or state.get("sql_query", "")
        prompt = f"Explain the following SQL query in plain, clear English. Focus on what data it retrieves:\n{query}"
        
        from langchain_core.messages import HumanMessage
        msg = HumanMessage(content=prompt)
        result = self.llm_service.generate_structured_output([msg], SQLExplanation)
        return {"explanation": result.explanation}

    def format_response(self, state: AgentState):
        if state.get("sql_generation_attempts", 0) >= 3 and not state.get("is_valid_sql"):
             msg = AIMessage(content=json.dumps({
                "error": "Failed to generate valid SQL after multiple attempts. Error: " + str(state.get("sql_errors"))
             }))
             return {"messages": [msg]}

        sql = state.get("optimized_sql") or state.get("sql_query")
        explanation = state.get("explanation", "")
        results = state.get("query_results", "")
        
        response_data = {
            "sql": sql,
            "explanation": explanation,
            "results": results
        }
        msg = AIMessage(content=json.dumps(response_data))
        return {"messages": [msg]}
