from abc import ABC, abstractmethod
import sqlite3
import os
from typing import List, Dict, Any, Tuple

class IDatabaseService(ABC):
    @abstractmethod
    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_schema(self) -> str:
        pass

class SQLiteDatabaseService(IDatabaseService):
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._initialize_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            raise ValueError(f"Database execution error: {str(e)}")

    def get_schema(self) -> str:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                
                schema_info = []
                for row in tables:
                    name, sql = row["name"], row["sql"]
                    if name != "sqlite_sequence":
                        schema_info.append(f"Table: {name}\nSchema: {sql}")
                return "\n\n".join(schema_info)
        except Exception as e:
            raise ValueError(f"Failed to retrieve schema: {str(e)}")

    def _initialize_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Create Departments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Departments (
                    DepartmentID INTEGER PRIMARY KEY AUTOINCREMENT,
                    DepartmentName TEXT NOT NULL
                )
            ''')
            # Create Employees table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Employees (
                    EmployeeID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Name TEXT NOT NULL,
                    DepartmentID INTEGER,
                    HireDate DATE,
                    Salary REAL,
                    FOREIGN KEY (DepartmentID) REFERENCES Departments(DepartmentID)
                )
            ''')
            # Create Customers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Customers (
                    CustomerID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Name TEXT NOT NULL,
                    State TEXT,
                    City TEXT
                )
            ''')

            # Insert sample data if tables are empty
            cursor.execute("SELECT COUNT(*) as count FROM Departments")
            if cursor.fetchone()["count"] == 0:
                cursor.executemany("INSERT INTO Departments (DepartmentName) VALUES (?)", [
                    ("Engineering",), ("Sales",), ("Marketing",), ("HR",)
                ])

            cursor.execute("SELECT COUNT(*) as count FROM Employees")
            if cursor.fetchone()["count"] == 0:
                cursor.executemany(
                    "INSERT INTO Employees (Name, DepartmentID, HireDate, Salary) VALUES (?, ?, ?, ?)", [
                    ("Alice Smith", 1, "2024-02-15", 95000),
                    ("Bob Jones", 2, "2023-11-01", 75000),
                    ("Charlie Brown", 1, "2024-01-10", 80000),
                    ("Diana Prince", 4, "2022-05-20", 90000)
                ])

            cursor.execute("SELECT COUNT(*) as count FROM Customers")
            if cursor.fetchone()["count"] == 0:
                cursor.executemany("INSERT INTO Customers (Name, State, City) VALUES (?, ?, ?)", [
                    ("Acme Corp", "California", "San Francisco"),
                    ("Globex", "New York", "New York City"),
                    ("Stark Industries", "California", "Los Angeles"),
                    ("Wayne Enterprises", "New Jersey", "Gotham")
                ])
            conn.commit()

# Dependency Injection setup
def get_db_service() -> IDatabaseService:
    db_path = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "..", "sample.db"))
    return SQLiteDatabaseService(db_path)
