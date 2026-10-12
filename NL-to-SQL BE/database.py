
import sqlite3
import re
from io import BytesIO

import pandas as pd


# ----------------------------------------
# DATABASE CONFIGURATION
# ----------------------------------------

TABLE_NAME = "uploaded_data"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


# ----------------------------------------
# FILE LOADING
# ----------------------------------------

def load_file(uploaded_file):
    """
    Read an uploaded Excel/CSV file and
    prepare it for SQLite.
    """

    if uploaded_file is None:
        raise ValueError("Please upload a file.")

    filename = uploaded_file.name.lower()

    # Read uploaded file bytes
    file_bytes = uploaded_file.getvalue()

    if len(file_bytes) > MAX_FILE_SIZE:
        raise ValueError(
            "File is too large. Maximum allowed size is 20 MB."
        )

    if not file_bytes:
        raise ValueError("Uploaded file is empty.")

    file_buffer = BytesIO(file_bytes)

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(file_buffer)

        elif filename.endswith(".xlsx"):
            df = pd.read_excel(
                file_buffer,
                engine="openpyxl"
            )

        else:
            raise ValueError(
                "Only CSV and XLSX files are supported."
            )

    except (ValueError, pd.errors.ParserError,
            pd.errors.EmptyDataError, UnicodeDecodeError) as error:
        raise ValueError(
            f"Unable to read uploaded file: {error}"
        ) from error

    if df.empty:
        raise ValueError(
            "Uploaded file contains no data."
        )

    # ------------------------------------
    # CLEAN COLUMN NAMES
    # ------------------------------------

    cleaned_columns = []
    used_names = set()

    for index, column in enumerate(df.columns):

        name = str(column).strip()

        # Replace empty/unnamed columns
        if (
            not name
            or name.lower().startswith("unnamed:")
        ):
            name = f"column_{index + 1}"

        # Replace unnecessary whitespace
        name = re.sub(r"\s+", "_", name)

        # Remove problematic characters
        name = re.sub(r"[^\w]", "_", name)

        # Make sure name is not empty
        if not name:
            name = f"column_{index + 1}"

        # Prefix numeric column names
        if name[0].isdigit():
            name = f"col_{name}"

        original_name = name
        counter = 1

        while name.lower() in used_names:
            name = f"{original_name}_{counter}"
            counter += 1

        cleaned_columns.append(name)
        used_names.add(name.lower())

    df.columns = cleaned_columns

    # ------------------------------------
    # NORMALIZE DATE AND DATA TYPES
    # ------------------------------------

    for column in df.columns:

        if pd.api.types.is_datetime64_any_dtype(df[column]):
            df[column] = df[column].dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        elif pd.api.types.is_bool_dtype(df[column]):
            df[column] = df[column].astype("Int64")

    # Replace Pandas missing values with
    # SQLite-compatible NULL values.
    df = df.astype(object).where(pd.notna(df), None)

    return df


# ----------------------------------------
# CREATE SQLITE DATABASE
# ----------------------------------------

def create_database(df):
    """
    Create a temporary in-memory SQLite
    database from a Pandas DataFrame.
    """

    if df is None or df.empty:
        raise ValueError(
            "Cannot create database from empty data."
        )

    connection = sqlite3.connect(
        ":memory:",
        check_same_thread=False,
        timeout=10
    )

    try:
        df.to_sql(
            name=TABLE_NAME,
            con=connection,
            if_exists="replace",
            index=False
        )

        # Make database read-only after loading.
        connection.execute(
            "PRAGMA query_only = ON"
        )

        return connection

    except Exception:
        connection.close()
        raise


# ----------------------------------------
# GET DATABASE SCHEMA
# ----------------------------------------

def get_schema(conn):
    """
    Return SQLite schema for Gemini AI.
    """

    cursor = conn.execute(
        f'PRAGMA table_info("{TABLE_NAME}")'
    )

    columns = cursor.fetchall()

    if not columns:
        raise ValueError(
            "No database columns found."
        )

    schema = []

    for column in columns:

        column_name = column[1]
        data_type = column[2]

        # Escape double quotes in identifiers.
        safe_name = column_name.replace('"', '""')

        schema.append(
            f'"{safe_name}" {data_type}'
        )

    return ", ".join(schema)


# ----------------------------------------
# EXECUTE SAFE SQL QUERY
# ----------------------------------------

def execute_query(conn, sql_query):
    """
    Execute AI-generated SQL through
    the security validator.

    Returns query results as DataFrame.
    """

    from sql_validator import execute_safe_query

    return execute_safe_query(
        conn,
        sql_query
    )


# ----------------------------------------
# DATABASE INFORMATION
# ----------------------------------------

def get_total_rows(conn):
    """
    Return number of records in uploaded table.
    """

    cursor = conn.execute(
        f'SELECT COUNT(*) FROM "{TABLE_NAME}"'
    )

    return cursor.fetchone()[0]


def get_preview(conn, limit=5):
    """
    Return first rows of uploaded dataset.
    """

    limit = max(1, min(int(limit), 100))

    return pd.read_sql_query(
        f'SELECT * FROM "{TABLE_NAME}" LIMIT ?',
        conn,
        params=(limit,)
    )
