import json
import re
import sqlglot
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
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
        
        # Build clean dialogue context without confusing raw JSON strings
        dialogue = []
        for m in messages:
            if isinstance(m, HumanMessage):
                dialogue.append(f"User: {m.content}")
            elif isinstance(m, AIMessage):
                try:
                    parsed = json.loads(m.content)
                    exp = parsed.get("explanation") or parsed.get("sql") or ""
                    if exp:
                        dialogue.append(f"Assistant: {exp[:150]}")
                except:
                    dialogue.append(f"Assistant: {m.content[:150]}")
                    
        history_context = "\n".join(dialogue)
        prompt = f"""You are an intent classifier for a database assistant.
Conversation so far:
{history_context}

Determine if the latest user request is related to querying, filtering, analyzing, or retrieving data from the database (employees, departments, customers).
Follow-ups (e.g., 'and in Los Angeles?', 'who has highest salary?', 'sort by date') in an ongoing database query conversation are IN SCOPE.
Out-of-scope requests are unrelated topics (sports, weather, recipes, poems, politics).

Return valid JSON with the single boolean field 'is_in_scope'.
"""
        try:
            result = self.llm_service.generate_structured_output([HumanMessage(content=prompt)], IntentDetection)
            return {"is_in_scope": result.is_in_scope}
        except Exception as e:
            # If the model answered with SQL or had a validation error on follow-up, it is definitely in-scope!
            err_str = str(e).lower()
            if "sql" in err_str or "customer" in err_str or "employee" in err_str or "city" in err_str:
                return {"is_in_scope": True}
            return {"is_in_scope": True}

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
        
        # Build clean conversation history so the model understands multi-turn follow-ups
        history_lines = []
        for m in messages[:-1]:
            if isinstance(m, HumanMessage):
                history_lines.append(f"User: {m.content}")
            elif isinstance(m, AIMessage):
                try:
                    parsed = json.loads(m.content)
                    if parsed.get("clarification"):
                        history_lines.append(f"Assistant Clarification Question: {parsed['clarification']}")
                    elif parsed.get("sql"):
                        history_lines.append(f"Generated SQL: {parsed['sql']}")
                except:
                    pass
        
        conversation_context = "\n".join(history_lines) if history_lines else "None"
        latest_user_request = messages[-1].content if messages else ""
        
        prompt = f"""You are a task-oriented SQL query assistant for SQLite.
Database Schema:
{schema}

Previous Conversation & Queries:
{conversation_context}

Latest User Request:
{latest_user_request}

Instructions:
1. Ambiguity Detection & Clarification Rules:
   - Carefully check if the user's latest request is truly AMBIGUOUS, underspecified, subjective, or missing required criteria.
   - Ambiguous queries include:
     * Subjective superlatives without metrics: "Show the best employee", "Find great customers", "Top performers", "Longest employee"
     * Completely ungrounded queries: "Show records", "Get data", "List everything" (entity or table unspecified)
   - NOT AMBIGUOUS queries (Generate SQL directly, do NOT ask clarification):
     * Queries with clear column filters, dates, aggregates, or standard business questions:
       - "Show all employees hired after 2023" -> NOT ambiguous (HireDate > '2023-12-31')
       - "List customers in California" -> NOT ambiguous (State = 'California')
       - "Average salary by department" -> NOT ambiguous (AVG(Salary) GROUP BY DepartmentID)
       - "Highest paid employee" -> NOT ambiguous (ORDER BY Salary DESC LIMIT 1)
       - "Count of employees" -> NOT ambiguous (COUNT(*))
   - If AMBIGUOUS and not resolved by previous conversation:
     * Set `is_ambiguous` = True.
     * In `clarification_question`, write a polite question offering concrete options based on schema columns (e.g. asking whether they mean salary, hire date, etc.).
     * Set `sql_query` = "".
   - If NOT AMBIGUOUS:
     * Set `is_ambiguous` = False.
     * Leave `clarification_question` null.
     * In `sql_query`, write the executable SQLite SELECT query.
2. Even if the user asks for a modification or destructive command (such as DROP, DELETE, INSERT, UPDATE, ALTER), output that exact SQL statement directly so our downstream security validator can evaluate it. Do NOT refuse or apologize.
3. NEVER hallucinate or invent tables or columns that do not exist in the provided schema. Only use tables: Departments, Employees, Customers and their exact columns.
4. If there were previous syntax errors or schema validation errors with your SQL, fix them. Previous errors: {errors}
"""
        try:
            result = self.llm_service.generate_structured_output([HumanMessage(content=prompt)], SQLGeneration)
            if result.is_ambiguous and result.clarification_question:
                return {
                    "is_ambiguous": True,
                    "clarification_message": result.clarification_question,
                    "sql_query": ""
                }
            sql_query = result.sql_query or ""
        except Exception as e:
            print(f"[generate_sql Error]: {e}")
            user_text = messages[-1].content.strip() if messages else ""
            sql_keywords = {"drop", "delete", "insert", "update", "alter", "truncate", "create"}
            words = set(re.findall(r'\b[a-zA-Z]+\b', user_text.lower()))
            if words.intersection(sql_keywords):
                sql_query = user_text
            else:
                return {
                    "is_ambiguous": False,
                    "clarification_message": None,
                    "sql_query": "",
                    "is_valid_sql": False,
                    "sql_errors": f"Language Model Service Error: {str(e)}",
                    "sql_generation_attempts": 3
                }
        
        attempts = state.get("sql_generation_attempts", 0) + 1
        return {
            "is_ambiguous": False,
            "clarification_message": None,
            "sql_query": sql_query, 
            "sql_generation_attempts": attempts
        }

    def ask_clarification(self, state: AgentState):
        question = state.get("clarification_message") or "Could you please clarify your request?"
        msg = AIMessage(content=json.dumps({
            "clarification": question,
            "explanation": question
        }))
        return {"messages": [msg]}

    def validate_sql(self, state: AgentState):
        if state.get("sql_errors"):
            return {
                "is_valid_sql": False,
                "sql_errors": state.get("sql_errors")
            }
        query = state.get("sql_query", "")
        if not query or not query.strip():
            return {
                "is_valid_sql": False,
                "sql_errors": "No SQL query could be generated for this request."
            }
        try:
            parsed = sqlglot.parse(query)
            if not parsed or parsed[0] is None:
                # Check for destructive keywords if unparsable
                q_lower = query.lower()
                if any(k in q_lower for k in ["drop", "delete", "insert", "update", "alter", "truncate"]):
                    return {
                        "is_valid_sql": False,
                        "sql_errors": f"Security Policy Violation: Only SELECT (read-only) queries are allowed. Destructive operation detected: '{query}'"
                    }
                return {"is_valid_sql": False, "sql_errors": f"Could not parse query: '{query}'"}

            statements = [s for s in parsed if s and not isinstance(s, (sqlglot.exp.Semicolon, sqlglot.exp.Comment))]
            for statement in statements:
                if not isinstance(statement, sqlglot.exp.Select):
                    return {
                        "is_valid_sql": False, 
                        "sql_errors": f"Security Policy Violation: Only SELECT (read-only) queries are allowed. Destructive operation detected: '{query}'"
                    }
            
            # Check for non-existent / hallucinated tables and columns using EXPLAIN
            try:
                with self.db_service._get_connection() as conn:
                    conn.cursor().execute(f"EXPLAIN {query}")
            except Exception as e:
                return {
                    "is_valid_sql": False,
                    "sql_errors": f"Schema Validation Error: {str(e)}. Available tables are: Departments, Employees, Customers."
                }

            return {"is_valid_sql": True, "sql_errors": None}
        except Exception as e:
            q_lower = query.lower()
            if any(k in q_lower for k in ["drop", "delete", "insert", "update", "alter", "truncate"]):
                return {
                    "is_valid_sql": False,
                    "sql_errors": f"Security Policy Violation: Only SELECT (read-only) queries are allowed. Destructive operation detected: '{query}'"
                }
            return {"is_valid_sql": False, "sql_errors": f"SQL syntax error: {str(e)}"}

    def optimize_sql(self, state: AgentState):
        query = state.get("sql_query", "")
        try:
            optimized = sqlglot.transpile(query, read="sqlite", write="sqlite", pretty=True)[0]
        except Exception:
            optimized = query
            
        return {"optimized_sql": optimized}

    def execute_query(self, state: AgentState):
        import time
        query = state.get("optimized_sql", "") or state.get("sql_query", "")
        try:
            start_t = time.perf_counter()
            results = self.db_service.execute_query(query)
            duration_ms = round((time.perf_counter() - start_t) * 1000, 2)
            return {
                "query_results": json.dumps(results[:50]),
                "execution_time_ms": duration_ms
            }
        except Exception as e:
            return {"query_results": f"Execution error: {e}", "execution_time_ms": 0.0}

    def generate_explanation(self, state: AgentState):
        query = state.get("optimized_sql", "") or state.get("sql_query", "")
        prompt = f"Explain the following SQL query in plain, clear English. Focus on what data it retrieves:\n{query}"
        
        msg = HumanMessage(content=prompt)
        try:
            result = self.llm_service.generate_structured_output([msg], SQLExplanation)
            return {"explanation": result.explanation}
        except Exception:
            return {"explanation": f"Retrieves database records using query: {query}"}

    def format_response(self, state: AgentState):
        if not state.get("is_valid_sql"):
             msg = AIMessage(content=json.dumps({
                "error": state.get("sql_errors") or "Query rejected by security policy."
             }))
             return {"messages": [msg]}

        sql = state.get("optimized_sql") or state.get("sql_query")
        explanation = state.get("explanation", "")
        results = state.get("query_results", "")
        
        response_data = {
            "sql": sql,
            "explanation": explanation,
            "results": results,
            "execution_time_ms": state.get("execution_time_ms", 0.0)
        }
        msg = AIMessage(content=json.dumps(response_data))
        return {"messages": [msg]}
