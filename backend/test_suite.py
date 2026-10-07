import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure backend directory is in python path
sys.path.insert(0, os.path.dirname(__file__))

from app.main import app
from app.services.db_service import get_db_service
from app.agent.nodes.nodes import AgentNodes
from app.agent.state import AgentState
from app.agent.graph import agent_app
from langchain_core.messages import HumanMessage


class TestDatabaseService(unittest.TestCase):
    """Unit tests for SQLite database service & schema retrieval."""

    def setUp(self):
        self.db = get_db_service()

    def test_schema_retrieval(self):
        schema = self.db.get_schema()
        self.assertIn("Departments", schema)
        self.assertIn("Employees", schema)
        self.assertIn("Customers", schema)

    def test_valid_select_query(self):
        results = self.db.execute_query("SELECT COUNT(*) as count FROM Employees")
        self.assertIsInstance(results, list)
        self.assertGreater(results[0]["count"], 0)

    def test_invalid_table_query_raises_error(self):
        with self.assertRaises(ValueError):
            self.db.execute_query("SELECT * FROM NonExistentTable")


class TestSQLValidationAndSecurity(unittest.TestCase):
    """Tests for SQLGlot AST validation, read-only enforcement, and anti-hallucination."""

    def setUp(self):
        self.nodes = AgentNodes()

    def test_valid_select_passes_validation(self):
        state = {
            "sql_query": "SELECT Name, Salary FROM Employees WHERE Salary > 50000",
            "messages": []
        }
        res = self.nodes.validate_sql(state)
        self.assertTrue(res.get("is_valid_sql"))
        self.assertIsNone(res.get("sql_errors"))

    def test_destructive_drop_blocked(self):
        state = {
            "sql_query": "DROP TABLE Employees;",
            "messages": []
        }
        res = self.nodes.validate_sql(state)
        self.assertFalse(res.get("is_valid_sql"))
        self.assertIn("Security Policy Violation", res.get("sql_errors", ""))

    def test_destructive_delete_blocked(self):
        state = {
            "sql_query": "DELETE FROM Customers WHERE CustomerID = 1;",
            "messages": []
        }
        res = self.nodes.validate_sql(state)
        self.assertFalse(res.get("is_valid_sql"))
        self.assertIn("Security Policy Violation", res.get("sql_errors", ""))

    def test_stacked_injection_blocked(self):
        state = {
            "sql_query": "SELECT * FROM Employees; DROP TABLE Employees;--",
            "messages": []
        }
        res = self.nodes.validate_sql(state)
        self.assertFalse(res.get("is_valid_sql"))
        self.assertIn("Security Policy Violation", res.get("sql_errors", ""))

    def test_hallucinated_table_caught_by_explain(self):
        state = {
            "sql_query": "SELECT * FROM Products WHERE Price > 100",
            "messages": []
        }
        res = self.nodes.validate_sql(state)
        self.assertFalse(res.get("is_valid_sql"))
        self.assertIn("no such table", res.get("sql_errors", "").lower())


class TestLangGraphAgentWorkflow(unittest.TestCase):
    """Integration tests for the LangGraph agent workflow."""

    def test_in_scope_query_generates_sql(self):
        state = {"messages": [HumanMessage(content="Show all departments")]}
        res = agent_app.invoke(state)
        self.assertTrue(res.get("is_valid_sql"))
        self.assertIsNotNone(res.get("optimized_sql"))
        self.assertIn("Departments", res.get("optimized_sql"))
        self.assertIsNotNone(res.get("query_results"))

    def test_out_of_scope_query_refused(self):
        state = {"messages": [HumanMessage(content="Who won the FIFA World Cup?")]}
        res = agent_app.invoke(state)
        self.assertFalse(res.get("is_in_scope", True))
        last_msg = res["messages"][-1].content
        self.assertIn("database", last_msg.lower())


class TestFastAPIChatEndpoint(unittest.TestCase):
    """End-to-end integration tests for the /api/chat HTTP endpoint."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_chat_valid_query(self):
        response = self.client.post(
            "/api/chat",
            json={"message": "List customers in California", "thread_id": "test-suite-1"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data.get("sql"))
        self.assertIn("Customers", data.get("sql"))
        self.assertIsNotNone(data.get("results"))
        self.assertIsNotNone(data.get("execution_time_ms"))

    def test_chat_destructive_query_blocked(self):
        response = self.client.post(
            "/api/chat",
            json={"message": "DROP TABLE Departments", "thread_id": "test-suite-2"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNotNone(data.get("error"))

    def test_chat_multi_turn_followup(self):
        thread_id = "test-multi-turn-suite"
        # Turn 1
        r1 = self.client.post(
            "/api/chat",
            json={"message": "Show customers in California", "thread_id": thread_id}
        )
        self.assertEqual(r1.status_code, 200)
        self.assertIsNotNone(r1.json().get("sql"))

        # Turn 2
        r2 = self.client.post(
            "/api/chat",
            json={"message": "and in Los Angeles only?", "thread_id": thread_id}
        )
        self.assertEqual(r2.status_code, 200)
        sql2 = r2.json().get("sql")
        self.assertIsNotNone(sql2)
        self.assertTrue("Los Angeles" in sql2 or "City" in sql2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
