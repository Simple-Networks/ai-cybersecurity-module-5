#!/usr/bin/env python3
"""
Generate SQLite database with HR violations data.

This script creates a SQLite database with a table called hr_violations
and populates it with fake employee violation data.
"""

import random
import sqlite3
from datetime import datetime, timedelta


def generate_database(db_name="hr_violations.db"):
    """
    Create SQLite database with hr_violations table and populate with fake data.

    Args:
        db_name: Name of the database file to create
    """
    # Connect to database (creates if doesn't exist)
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    # Drop table if exists (for fresh start)
    cursor.execute("DROP TABLE IF EXISTS hr_violations")

    # Create hr_violations table
    cursor.execute("""
        CREATE TABLE hr_violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            employee_name TEXT NOT NULL,
            department TEXT NOT NULL,
            violation_count INTEGER NOT NULL,
            last_violation_date TEXT,
            violation_type TEXT,
            severity TEXT
        )
    """)

    # Define fake data
    departments = [
        "Engineering",
        "Sales",
        "Marketing",
        "HR",
        "Finance",
        "Operations",
        "Customer Service",
        "IT",
        "Legal",
        "R&D",
    ]

    violation_types = [
        "Late Arrival",
        "Unauthorized Absence",
        "Policy Breach",
        "Code of Conduct",
        "Safety Violation",
        "Dress Code",
        "Confidentiality Breach",
        "Harassment",
        "Insubordination",
        "Equipment Misuse",
        "Time Theft",
        "Conflict of Interest",
    ]

    severities = ["Minor", "Moderate", "Serious", "Critical"]

    first_names = [
        "John",
        "Jane",
        "Michael",
        "Sarah",
        "David",
        "Emily",
        "James",
        "Lisa",
        "Robert",
        "Mary",
        "William",
        "Jennifer",
        "Richard",
        "Linda",
        "Joseph",
        "Patricia",
        "Thomas",
        "Barbara",
        "Christopher",
        "Susan",
        "Daniel",
        "Jessica",
        "Matthew",
        "Karen",
        "Anthony",
        "Nancy",
        "Mark",
        "Betty",
        "Donald",
        "Helen",
    ]

    last_names = [
        "Smith",
        "Johnson",
        "Williams",
        "Brown",
        "Jones",
        "Garcia",
        "Miller",
        "Davis",
        "Rodriguez",
        "Martinez",
        "Hernandez",
        "Lopez",
        "Wilson",
        "Anderson",
        "Thomas",
        "Taylor",
        "Moore",
        "Jackson",
        "Martin",
        "Lee",
        "Perez",
        "Thompson",
        "White",
        "Harris",
        "Sanchez",
        "Clark",
        "Ramirez",
        "Lewis",
        "Robinson",
        "Walker",
    ]

    # Generate fake employee violation records
    employees = []
    num_employees = 50

    for i in range(num_employees):
        employee_id = f"EMP{1000 + i}"
        employee_name = f"{random.choice(first_names)} {random.choice(last_names)}"
        department = random.choice(departments)

        # Weight violation counts towards lower numbers (most employees have few violations)
        violation_count = random.choices(
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            weights=[5, 20, 15, 12, 10, 8, 6, 4, 3, 2, 1],
        )[0]

        # Generate last violation date (within last 365 days)
        if violation_count > 0:
            days_ago = random.randint(1, 365)
            last_violation_date = (datetime.now() - timedelta(days=days_ago)).strftime(
                "%Y-%m-%d"
            )
        else:
            last_violation_date = None

        violation_type = random.choice(violation_types) if violation_count > 0 else None

        # Severity tends to increase with violation count
        if violation_count == 0:
            severity = None
        elif violation_count <= 2:
            severity = random.choice(["Minor", "Minor", "Moderate"])
        elif violation_count <= 5:
            severity = random.choice(["Moderate", "Moderate", "Serious"])
        else:
            severity = random.choice(["Serious", "Serious", "Critical"])

        employees.append(
            (
                employee_id,
                employee_name,
                department,
                violation_count,
                last_violation_date,
                violation_type,
                severity,
            )
        )

    # Insert data into table
    cursor.executemany(
        """
        INSERT INTO hr_violations (
            employee_id, employee_name, department, violation_count,
            last_violation_date, violation_type, severity
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        employees,
    )

    # Commit changes
    conn.commit()

    # Display summary
    cursor.execute("SELECT COUNT(*) FROM hr_violations")
    total_records = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(violation_count) FROM hr_violations")
    total_violations = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM hr_violations WHERE violation_count > 0")
    employees_with_violations = cursor.fetchone()[0]

    print(f"✓ Database '{db_name}' created successfully!")
    print(f"✓ Total employee records: {total_records}")
    print(f"✓ Employees with violations: {employees_with_violations}")
    print(f"✓ Total violations: {total_violations}")

    # Display sample data
    print("\nSample records:")
    cursor.execute("""
        SELECT employee_id, employee_name, department, violation_count, severity
        FROM hr_violations
        WHERE violation_count > 0
        ORDER BY violation_count DESC
        LIMIT 10
    """)

    print(f"{'ID':<10} {'Name':<20} {'Department':<15} {'Violations':<12} {'Severity'}")
    print("-" * 75)
    for row in cursor.fetchall():
        print(f"{row[0]:<10} {row[1]:<20} {row[2]:<15} {row[3]:<12} {row[4]}")

    # Close connection
    conn.close()


if __name__ == "__main__":
    generate_database()
    print("\n✓ Database generation complete!")
