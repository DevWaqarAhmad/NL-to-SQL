import time
import pandas as pd


# ----------------------------------------
# CONFIGURATION
# ----------------------------------------

MAX_EXECUTION_TIME = 10
MAX_RESULT_ROWS = 1000



# ----------------------------------------
# SQL VALIDATION
# ----------------------------------------

def validate_sql(sql):
    """
    Validate AI generated SQL.

    Allowed:
    - SELECT
    - WITH (CTE)

    Block:
    - INSERT
    - UPDATE
    - DELETE
    - DROP
    - ALTER
    """

    if not isinstance(sql, str):

        raise ValueError(
            "SQL must be text."
        )


    sql = sql.strip()


    if not sql:

        raise ValueError(
            "SQL query is empty."
        )


    normalized = sql.lower()



    # Only SELECT / WITH

    if not (
        normalized.startswith("select")
        or normalized.startswith("with")
    ):

        raise ValueError(
            "Only SELECT queries are allowed."
        )



    # Block multiple queries

    if ";" in sql.rstrip("; \n\t"):

        raise ValueError(
            "Multiple SQL statements are not allowed."
        )



    # Dangerous commands

    blocked_keywords = [

        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "truncate",
        "create",
        "replace",
        "attach",
        "detach"

    ]


    for keyword in blocked_keywords:

        if keyword in normalized:

            raise ValueError(
                f"Blocked SQL keyword: {keyword}"
            )



    # Only uploaded_data table

    if "uploaded_data" not in normalized:

        raise ValueError(
            "Only uploaded_data table can be queried."
        )


    return sql




# ----------------------------------------
# SAFE QUERY EXECUTION
# ----------------------------------------

def execute_safe_query(connection, sql):

    """
    Execute validated SQL safely.
    Returns pandas DataFrame.
    """


    sql = validate_sql(sql)



    start_time = time.time()



    try:


        result = connection.execute(
            sql
        ).fetchdf()



        execution_time = (
            time.time() - start_time
        )



        if execution_time > MAX_EXECUTION_TIME:

            raise TimeoutError(
                "Query execution timeout."
            )



        # Limit output rows

        if len(result) > MAX_RESULT_ROWS:

            result = result.head(
                MAX_RESULT_ROWS
            )

            result.attrs["truncated"] = True



        return result



    except Exception as error:


        raise Exception(
            f"SQL execution failed: {error}"
        )