
import sqlite3
import time
import threading
import pandas as pd


# ----------------------------------------
# CONFIGURATION
# ----------------------------------------

MAX_EXECUTION_TIME = 10  # Seconds
MAX_RESULT_ROWS = 1000

# Protect concurrent operations on the same
# SQLite connection in our local Streamlit app.
_DB_LOCK = threading.RLock()


# ----------------------------------------
# SQL VALIDATION
# ----------------------------------------

def validate_sql(sql):
    """
    Validate AI-generated SQL before execution.
    Only read-only SELECT / WITH queries are allowed.
    """

    if not isinstance(sql, str):
        raise ValueError("SQL query must be a string.")

    sql = sql.strip()

    if not sql:
        raise ValueError("SQL query is empty.")

    if sql.upper() == "CANNOT_ANSWER":
        raise ValueError(
            "This question cannot be answered using "
            "the uploaded data."
        )

    normalized = sql.lower()

    if not (
        normalized.startswith("select ")
        or normalized.startswith("select\n")
        or normalized.startswith("select\t")
        or normalized.startswith("with ")
        or normalized.startswith("with\n")
        or normalized.startswith("with\t")
    ):
        raise ValueError(
            "Only SELECT queries are allowed."
        )

    # Reject multiple statements. SQLite's
    # execute() will also enforce this.
    if ";" in sql.rstrip("; \n\r\t"):
        raise ValueError(
            "Multiple SQL statements are not allowed."
        )

    return sql


# ----------------------------------------
# SAFE SQL EXECUTION
# ----------------------------------------

def execute_safe_query(connection, sql):
    """
    Execute AI-generated SQL with:
      - SQLite read-only mode
      - SQLite authorizer
      - Execution timeout
      - Result row limit
    """

    sql = validate_sql(sql)

    allowed_actions = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
    }

    if hasattr(sqlite3, "SQLITE_RECURSIVE"):
        allowed_actions.add(
            sqlite3.SQLITE_RECURSIVE
        )

    def authorizer(action, arg1, arg2, db_name, source):
        """
        Allow reading uploaded_data only.
        Block modifying database operations.
        """

        if action == sqlite3.SQLITE_READ:
            if (
                db_name != "main"
                or arg1 != "uploaded_data"
            ):
                return sqlite3.SQLITE_DENY

            return sqlite3.SQLITE_OK

        if action in allowed_actions:
            return sqlite3.SQLITE_OK

        return sqlite3.SQLITE_DENY

    start_time = time.monotonic()

    def progress_handler():
        elapsed = time.monotonic() - start_time

        if elapsed > MAX_EXECUTION_TIME:
            return 1

        return 0

    with _DB_LOCK:

        # Enable read-only mode BEFORE installing
        # the authorizer.
        connection.execute(
            "PRAGMA query_only = ON"
        )

        connection.set_authorizer(authorizer)

        connection.set_progress_handler(
            progress_handler,
            1000
        )

        try:
            # Execute one SQL statement only.
            cursor = connection.execute(sql)

            if cursor.description is None:
                raise ValueError(
                    "Query did not return any results."
                )

            columns = [
                item[0] for item in cursor.description
            ]

            # Fetch at most 1001 rows to detect
            # whether the display limit is reached.
            rows = cursor.fetchmany(
                MAX_RESULT_ROWS + 1
            )

            truncated = len(rows) > MAX_RESULT_ROWS

            if truncated:
                rows = rows[:MAX_RESULT_ROWS]

            result = pd.DataFrame(
                rows,
                columns=columns
            )

            if truncated:
                result.attrs["truncated"] = True

            return result

        except sqlite3.OperationalError as error:
            if "interrupted" in str(error).lower():
                raise TimeoutError(
                    "SQL query exceeded the "
                    f"{MAX_EXECUTION_TIME}-second limit."
                ) from error

            raise

        finally:
            connection.set_progress_handler(
                None, 0
            )

            connection.set_authorizer(None)
