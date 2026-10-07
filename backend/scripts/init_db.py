import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "sample.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
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
    cursor.execute("SELECT COUNT(*) FROM Departments")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO Departments (DepartmentName) VALUES (?)", [
            ("Engineering",), ("Sales",), ("Marketing",), ("HR",)
        ])

    cursor.execute("SELECT COUNT(*) FROM Employees")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO Employees (Name, DepartmentID, HireDate, Salary) VALUES (?, ?, ?, ?)", [
            ("Alice Smith", 1, "2024-02-15", 95000),
            ("Bob Jones", 2, "2023-11-01", 75000),
            ("Charlie Brown", 1, "2024-01-10", 80000),
            ("Diana Prince", 4, "2022-05-20", 90000)
        ])

    cursor.execute("SELECT COUNT(*) FROM Customers")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("INSERT INTO Customers (Name, State, City) VALUES (?, ?, ?)", [
            ("Acme Corp", "California", "San Francisco"),
            ("Globex", "New York", "New York City"),
            ("Stark Industries", "California", "Los Angeles"),
            ("Wayne Enterprises", "New Jersey", "Gotham")
        ])

    conn.commit()
    conn.close()
    print("Database initialized successfully at", DB_PATH)

if __name__ == "__main__":
    init_db()
