"""
DataPilot AI — SQL Validation and Execution
Purpose:
    Validate AI-generated DuckDB SQL before execution.
Rules:
    - One SQL statement only.
    - SELECT queries only.
    - Read-only CTEs are supported.
    - Only uploaded_data may be queried.
    - External files, table functions, and unknown
      SQL functions are not permitted.
    - Return a maximum of 1000 result rows.
Important:
    This validator is a defense-in-depth component,
    not a complete security sandbox.
    MAX_EXECUTION_TIME is a post-execution guard.
    It does not interrupt a running DuckDB query.
"""
import time
import pandas as pd
from sqlglot import exp, parse
from sqlglot.errors import ParseError
# =========================================
# CONFIGURATION
# =========================================
MAX_EXECUTION_TIME = 10
MAX_RESULT_ROWS = 1000
MAX_SQL_LENGTH = 20_000
ALLOWED_TABLE = "uploaded_data"
# Restrict SQL functions to common analytical
# operations needed by Data Explorer.
ALLOWED_FUNCTIONS = {
    "COUNT",
    "SUM",
    "AVG",
    "AVERAGE",
    "MIN",
    "MAX",
    "ROUND",
    "ABS",
    "CEIL",
    "CEILING",
    "FLOOR",
    "LOWER",
    "UPPER",
    "TRIM",
    "LTRIM",
    "RTRIM",
    "LENGTH",
    "CHAR_LENGTH",
    "CONCAT",
    "SUBSTRING",
    "SUBSTR",
    "REPLACE",
    "COALESCE",
    "NULLIF",
    "IFNULL",
    "TRY_CAST",
    "CAST",
    "DATE_TRUNC",
    "DATE_PART",
    "EXTRACT",
    "YEAR",
    "MONTH",
    "DAY",
    "HOUR",
    "MINUTE",
    "SECOND",
    "STRFTIME",
    "STRPTIME",
    "DATEDIFF",
    "DATE_DIFF",
    "DATEADD",
    "DATE_ADD",
    "CURRENT_DATE",
    "CURRENT_TIMESTAMP",
    "NOW",
    "COUNT_IF",
    "STDDEV",
    "STDDEV_SAMP",
    "STDDEV_POP",
    "VARIANCE",
    "VAR_SAMP",
    "VAR_POP",
    "MEDIAN",
    "MODE",
    "QUANTILE_CONT",
    "QUANTILE_DISC",
    "ROW_NUMBER",
    "RANK",
    "DENSE_RANK",
    "LAG",
    "LEAD",
    "FIRST_VALUE",
    "LAST_VALUE",
    "NTILE",
    "GREATEST",
    "LEAST",
    "POWER",
    "POW",
    "SQRT",
    "MOD",
    "ISNAN",
    "ISINF",
}
# =========================================
# SQL PARSING
# =========================================
def _parse_sql(sql):
    """
    Parse exactly one DuckDB SQL statement.
    A SQL parser avoids unreliable checks such
    as searching for forbidden words inside
    column names or string values.
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
    if len(sql) > MAX_SQL_LENGTH:
        raise ValueError(
            "SQL query exceeds the maximum length."
        )
    try:
        statements = parse(
            sql,
            read="duckdb",
            error_level="RAISE",
        )
    except ParseError as error:
        raise ValueError(
            f"Invalid SQL syntax: {error}"
        ) from error
    statements = [
        statement
        for statement in statements
        if statement is not None
    ]
    if len(statements) != 1:
        raise ValueError(
            "Exactly one SQL statement is allowed."
        )
    statement = statements[0]
    if not isinstance(statement, exp.Select):
        raise ValueError(
            "Only SELECT queries are allowed."
        )
    return statement
# =========================================
# FUNCTION VALIDATION
# =========================================
def _function_name(function):
    """
    Extract the normalized SQL function name.
    """
    if isinstance(function, exp.Anonymous):
        return str(function.name).upper()
    return str(
        function.sql_name()
    ).upper()
def _validate_functions(statement):
    """
    Restrict executable SQL functions.
    Unknown or potentially unsafe functions,
    including external-data readers, are rejected.
    """
    for function in statement.find_all(exp.Func):
        # SQLGlot may represent boolean operators as Func nodes.
        # AND, OR, and NOT are SQL syntax, not callable functions.
        if isinstance(function, (exp.And, exp.Or, exp.Not)):
            continue
        name = _function_name(function)
        if name not in ALLOWED_FUNCTIONS:
            raise ValueError(
                f"SQL function is not allowed: {name}"
            )
# =========================================
# TABLE VALIDATION
# =========================================
def _validate_tables(statement):
    """
    Allow references only to uploaded_data
    and CTEs declared by the current query.
    Database/catalog qualification is rejected.
    """
    cte_names = set()
    for cte in statement.find_all(exp.CTE):
        name = cte.alias_or_name
        if not name:
            raise ValueError(
                "Every CTE must have a name."
            )
        normalized_name = name.lower()
        if normalized_name == ALLOWED_TABLE:
            raise ValueError(
                "A CTE cannot override uploaded_data."
            )
        if normalized_name in cte_names:
            raise ValueError(
                "Duplicate CTE name."
            )
        cte_names.add(normalized_name)
    allowed_names = {
        ALLOWED_TABLE,
        *cte_names,
    }
    found_uploaded_data = False
    tables = list(
        statement.find_all(exp.Table)
    )
    if not tables:
        raise ValueError(
            "The query must reference uploaded_data."
        )
    for table in tables:
        if table.db or table.catalog:
            raise ValueError(
                "Qualified database or catalog "
                "references are not allowed."
            )
        table_name = str(
            table.name
        ).lower()
        if table_name not in allowed_names:
            raise ValueError(
                f"Table is not allowed: {table.name}"
            )
        if table_name == ALLOWED_TABLE:
            found_uploaded_data = True
    if not found_uploaded_data:
        raise ValueError(
            "The query must reference uploaded_data."
        )
# =========================================
# READ-ONLY STRUCTURE VALIDATION
# =========================================
def _validate_structure(statement):
    """
    Reject SQL constructs that do not belong
    in a supported read-only analytical query.
    """
    # SELECT INTO is not permitted.
    if statement.args.get("into") is not None:
        raise ValueError(
            "SELECT INTO is not allowed."
        )
    # Locking clauses are not permitted.
    if statement.args.get("locks"):
        raise ValueError(
            "SQL locking clauses are not allowed."
        )
    for with_clause in statement.find_all(exp.With):
        if with_clause.args.get("recursive"):
            raise ValueError(
                "Recursive CTEs are not allowed."
            )
    # Keep the accepted query grammar narrow.
    # UNION/INTERSECT/EXCEPT can be enabled later
    # with separate validation and tests.
    if any(
        isinstance(
            node,
            (
                exp.Union,
                exp.Intersect,
                exp.Except,
            ),
        )
        for node in statement.walk()
    ):
        raise ValueError(
            "Set operations are not supported."
        )
    # Reject table-valued functions and other
    # nonstandard FROM/JOIN relation expressions.
    for relation in statement.find_all(
        exp.From,
        exp.Join,
    ):
        target = relation.this
        if target is None:
            continue
        if not isinstance(
            target,
            (
                exp.Table,
                exp.Subquery,
            ),
        ):
            raise ValueError(
                "Unsupported SQL data source."
            )
    _validate_tables(statement)
    _validate_functions(statement)
# =========================================
# PUBLIC SQL VALIDATION
# =========================================
def validate_sql(sql):
    """
    Validate an AI-generated SQL query.
    Returns the validated SQL string.
    Raises ValueError for unsupported queries.
    """
    statement = _parse_sql(sql)
    _validate_structure(statement)
    # Return normalized DuckDB SQL from the AST,
    # rather than executing the raw LLM response.
    validated_sql = statement.sql(
        dialect="duckdb",
    )
    return validated_sql
# =========================================
# SAFE QUERY EXECUTION
# =========================================
def execute_safe_query(connection, sql):
    """
    Execute a validated analytical query.
    Returns:
        pandas.DataFrame
    The outer LIMIT prevents loading an
    unrestricted number of result rows into
    a pandas DataFrame.
    Result metadata:
        result.attrs["truncated"]
        result.attrs["execution_time"]
    Note:
        The execution-duration check below
        is not a hard timeout.
    """
    validated_sql = validate_sql(sql)
    # Fetch one extra row to determine whether
    # the result exceeds the public row limit.
    fetch_limit = MAX_RESULT_ROWS + 1
    # The validated query is an analytical SELECT.
    # Wrapping it preserves its result columns
    # and applies an outer database-side limit.
    bounded_sql = (
        "SELECT * FROM ("
        f"{validated_sql}"
        ") AS datapilot_limited_result "
        f"LIMIT {fetch_limit}"
    )
    started_at = time.monotonic()
    try:
        result = connection.execute(
            bounded_sql
        ).fetchdf()
    except Exception as error:
        raise RuntimeError(
            f"SQL execution failed: {error}"
        ) from error
    execution_time = (
        time.monotonic() - started_at
    )
    # Post-execution duration guard:
    # this does not stop a query while running.
    if execution_time > MAX_EXECUTION_TIME:
        raise TimeoutError(
            "Query exceeded the configured "
            "execution duration."
        )
    truncated = (
        len(result) > MAX_RESULT_ROWS
    )
    if truncated:
        result = result.iloc[
            :MAX_RESULT_ROWS
        ].copy()
    result.attrs["truncated"] = truncated
    result.attrs["execution_time"] = (
        execution_time
    )
    return result
