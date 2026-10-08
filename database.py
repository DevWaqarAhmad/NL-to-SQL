
import sqlite3
import pandas as pd
from io import BytesIO


def load_file(uploaded_file):
    """Read an uploaded CSV or Excel file."""

    file_name = uploaded_file.name.lower()

    if file_name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)

    elif file_name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)

    else:
        raise ValueError("Only CSV and XLSX files are supported.")

    if df.empty:
        raise ValueError("Uploaded file contains no data.")

    # Clean column names
    df.columns = [
        str(col).strip() for col in df.columns
    ]

    # Handle empty or duplicate column names
    columns = []
    used = set()

    for i, col in enumerate(df.columns):
        name = col if col else f"column_{i + 1}"
        original = name
        counter = 1

        while name.lower() in used:
            name = f"{original}_{counter}"
            counter += 1

        columns.append(name)
        used.add(name.lower())

    df.columns = columns

    return df



def create_database(df):
    """Create an in-memory SQLite database."""

    conn = sqlite3.connect(
        ":memory:",
        check_same_thread=False
    )

    df.to_sql(
        name="uploaded_data",
        con=conn,
        if_exists="replace",
        index=False
    )

    return conn



def get_schema(conn):
    """Retrieve SQLite table schema."""

    cursor = conn.execute(
        "PRAGMA table_info(uploaded_data)"
    )

    columns = cursor.fetchall()

    schema = []

    for col in columns:
        column_name = col[1]
        data_type = col[2]

        schema.append(
            f'"{column_name}" {data_type}'
        )

    return ", ".join(schema)


def execute_query(conn, sql_query):
    """
    Execute a SQL query and return actual results.

    Security validation will be integrated
    in the next development step.
    """

    results = pd.read_sql_query(
        sql_query,
        conn
    )

    return results
