
from io import BytesIO
from pathlib import Path
import re

import duckdb
import pandas as pd


# =========================================
# CONFIGURATION
# =========================================

TABLE_NAME = "uploaded_data"

MAX_COLUMNS = 100

SUPPORTED_COLUMN_TYPES = {
    "text": "string",
    "string": "string",
    "str": "string",

    "integer": "Int64",
    "int": "Int64",

    "decimal": "Float64",
    "float": "Float64",
    "number": "Float64",

    "boolean": "boolean",
    "bool": "boolean",

    "date": "datetime64[ns]",
    "datetime": "datetime64[ns]",
}


# =========================================
# DATA ENGINE
# =========================================

class DataEngine:
    """
    DataPilot AI dataset engine.

    Supports:
        1. CSV uploads
        2. Excel uploads
        3. Creating empty datasets
        4. DuckDB synchronization
        5. Schema inspection
        6. Dataset preview
        7. DataFrame access

    The DuckDB table name remains uploaded_data
    for both uploaded and newly created datasets.
    """

    def __init__(self):
        self.connection = duckdb.connect(
            database=":memory:"
        )

        self.current_df = None

    # =====================================
    # NORMALIZE COLUMN NAMES
    # =====================================

    @staticmethod
    def normalize_column_name(name, index=None):
        """
        Normalize column names while preserving
        existing upload conventions.

        Spaces become underscores.
        Actual cell values are never changed.
        """

        cleaned = str(name).strip()

        cleaned = cleaned.replace(" ", "_")

        if (
            not cleaned
            or cleaned.lower().startswith("unnamed:")
        ):
            if index is None:
                raise ValueError(
                    "Column name cannot be empty."
                )

            cleaned = f"Column_{index + 1}"

        if len(cleaned) > 128:
            raise ValueError(
                "Column names cannot exceed "
                "128 characters."
            )

        if "\x00" in cleaned:
            raise ValueError(
                "Column name contains "
                "an invalid character."
            )

        return cleaned

    # =====================================
    # VALIDATE COLUMN NAMES
    # =====================================

    @staticmethod
    def validate_column_names(columns):
        """
        Reject duplicate or invalid names.

        Case-insensitive duplicates are rejected
        to avoid ambiguity in DuckDB.
        """

        if not columns:
            raise ValueError(
                "At least one column is required."
            )

        if len(columns) > MAX_COLUMNS:
            raise ValueError(
                f"Maximum {MAX_COLUMNS} columns "
                "are supported."
            )

        normalized = [
            str(column).casefold()
            for column in columns
        ]

        if len(normalized) != len(set(normalized)):
            raise ValueError(
                "Duplicate column names detected. "
                "Please use unique column names."
            )

        return True

    # =====================================
    # READ UPLOADED FILE
    # =====================================

    def load_file(self, uploaded_file):
        """
        Load a CSV or Excel file.

        Existing upload behavior is preserved.
        """

        if uploaded_file is None:
            raise ValueError(
                "No file uploaded."
            )

        filename = getattr(
            uploaded_file,
            "name",
            None,
        )

        if not filename:
            raise ValueError(
                "Uploaded file has no filename."
            )

        extension = Path(
            str(filename)
        ).suffix.lower()

        if extension not in {
            ".csv",
            ".xlsx",
        }:
            raise ValueError(
                "Only CSV and XLSX files "
                "are supported."
            )

        if hasattr(
            uploaded_file,
            "getvalue",
        ):
            content = uploaded_file.getvalue()

        else:
            uploaded_file.seek(0)
            content = uploaded_file.read()

        if not content:
            raise ValueError(
                "Uploaded file is empty."
            )

        buffer = BytesIO(content)

        if extension == ".csv":
            try:
                df = pd.read_csv(
                    buffer,
                    encoding="utf-8-sig",
                )

            except UnicodeDecodeError:
                buffer.seek(0)

                df = pd.read_csv(
                    buffer,
                    encoding="cp1252",
                )

        else:
            df = pd.read_excel(
                buffer,
                engine="openpyxl",
            )

        if df.empty:
            raise ValueError(
                "Uploaded file contains "
                "no data rows."
            )

        cleaned_columns = []

        for index, column in enumerate(
            df.columns
        ):
            cleaned = (
                self.normalize_column_name(
                    column,
                    index=index,
                )
            )

            cleaned_columns.append(cleaned)

        self.validate_column_names(
            cleaned_columns
        )

        df.columns = cleaned_columns

        self.reload_database(df)

        return df.copy()

    # =====================================
    # CREATE EMPTY DATASET
    # =====================================

    def create_empty_dataset(self, columns):
        """
        Create a new empty dataset with
        specified columns and data types.

        Example:

        columns = [
            {"name": "Name", "type": "text"},
            {"name": "Age", "type": "integer"},
            {"name": "Salary", "type": "decimal"},
            {"name": "Active", "type": "boolean"},
            {"name": "Join_Date", "type": "date"}
        ]

        Returns:
            Empty pandas DataFrame with defined
            columns and supported data types.

        The dataset contains zero rows.
        """

        if not isinstance(columns, list):
            raise ValueError(
                "Columns must be provided as a list."
            )

        if not columns:
            raise ValueError(
                "At least one column is required."
            )

        if len(columns) > MAX_COLUMNS:
            raise ValueError(
                f"Maximum {MAX_COLUMNS} columns "
                "are supported."
            )

        prepared_columns = []
        column_names = []

        for index, column in enumerate(columns):
            if not isinstance(column, dict):
                raise ValueError(
                    f"Invalid column definition "
                    f"at position {index + 1}."
                )

            raw_name = column.get("name")

            if (
                not isinstance(raw_name, str)
                or not raw_name.strip()
            ):
                raise ValueError(
                    f"Column {index + 1} "
                    "requires a valid name."
                )

            name = self.normalize_column_name(
                raw_name
            )

            raw_type = column.get(
                "type",
                "text",
            )

            if not isinstance(raw_type, str):
                raise ValueError(
                    f"Invalid data type for "
                    f"column '{name}'."
                )

            type_name = (
                raw_type.strip().lower()
            )

            if type_name not in SUPPORTED_COLUMN_TYPES:
                raise ValueError(
                    f"Unsupported data type "
                    f"'{raw_type}' for column '{name}'."
                )

            pandas_dtype = (
                SUPPORTED_COLUMN_TYPES[type_name]
            )

            prepared_columns.append(
                {
                    "name": name,
                    "dtype": pandas_dtype,
                }
            )

            column_names.append(name)

        self.validate_column_names(
            column_names
        )

        # Create an empty DataFrame with
        # explicitly defined column types.
        empty_columns = {}

        for column in prepared_columns:
            empty_columns[column["name"]] = (
                pd.Series(
                    dtype=column["dtype"]
                )
            )

        df = pd.DataFrame(empty_columns)

        # Register the zero-row DataFrame
        # as the DuckDB dataset table.
        self.reload_database(df)

        return df.copy()

    # =====================================
    # SYNCHRONIZE DATAFRAME WITH DUCKDB
    # =====================================

    def reload_database(self, df):
        """
        Synchronize a DataFrame with DuckDB.

        Supports both empty and populated
        DataFrames.

        Updates the current DataFrame only
        after successful database synchronization.
        """

        if df is None:
            raise ValueError(
                "No dataframe provided."
            )

        if not isinstance(
            df,
            pd.DataFrame,
        ):
            raise TypeError(
                "Expected a pandas DataFrame."
            )

        if len(df.columns) == 0:
            raise ValueError(
                "Dataframe must contain "
                "at least one column."
            )

        self.validate_column_names(
            list(df.columns)
        )

        updated_df = (
            df.copy(deep=True)
            .reset_index(drop=True)
        )

        temporary_name = "_datapilot_temp"

        try:
            self.connection.register(
                temporary_name,
                updated_df,
            )

            self.connection.execute(
                "BEGIN TRANSACTION"
            )

            try:
                self.connection.execute(
                    f"""
                    CREATE OR REPLACE TABLE
                    {TABLE_NAME}
                    AS
                    SELECT *
                    FROM {temporary_name}
                    """
                )

                self.connection.execute(
                    "COMMIT"
                )

            except Exception:
                self.connection.execute(
                    "ROLLBACK"
                )
                raise

            self.current_df = updated_df

            return True

        finally:
            try:
                self.connection.unregister(
                    temporary_name
                )
            except Exception:
                pass

    # =====================================
    # DATABASE SCHEMA
    # =====================================

    def get_schema(self):
        """
        Return the DuckDB schema.

        Example:
            Name VARCHAR,
            Age BIGINT,
            Salary DOUBLE

        Works for empty datasets too.
        """

        schema = self.connection.execute(
            f"DESCRIBE {TABLE_NAME}"
        ).fetchdf()

        columns = []

        for _, row in schema.iterrows():
            columns.append(
                f"{row['column_name']} "
                f"{row['column_type']}"
            )

        return ", ".join(columns)

    # =====================================
    # QUERY EXECUTION
    # =====================================

    def execute_query(self, sql):
        """
        Execute trusted application SQL only.

        AI-generated SQL must be validated by
        the separate SQL validation layer.
        """

        if (
            not isinstance(sql, str)
            or not sql.strip()
        ):
            raise ValueError(
                "SQL query is required."
            )

        return self.connection.execute(
            sql
        ).fetchdf()

    # =====================================
    # DATA PREVIEW
    # =====================================

    def preview(self, limit=10):
        """
        Preview rows from the current dataset.

        Returns an empty DataFrame with
        columns when the dataset has zero rows.
        """

        limit = int(limit)

        if limit < 1 or limit > 1000:
            raise ValueError(
                "Preview limit must be "
                "between 1 and 1000."
            )

        return self.connection.execute(
            f"""
            SELECT *
            FROM {TABLE_NAME}
            LIMIT ?
            """,
            [limit],
        ).fetchdf()

    # =====================================
    # CURRENT DATAFRAME
    # =====================================

    def get_dataframe(self):
        """
        Return a copy of the current dataset.
        """

        if self.current_df is None:
            raise ValueError(
                "No dataset loaded."
            )

        return self.current_df.copy(
            deep=True
        )

    # =====================================
    # CLOSE DATABASE
    # =====================================

    def close(self):
        self.connection.close()
        self.current_df = None
