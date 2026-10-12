
from io import BytesIO
from pathlib import Path

import duckdb
import pandas as pd


TABLE_NAME = "uploaded_data"


class DataEngine:

    def __init__(self):
        self.connection = duckdb.connect(
            database=":memory:"
        )
        self.current_df = None

    # --------------------------------
    # READ UPLOADED FILE
    # --------------------------------

    def load_file(self, uploaded_file):

        if uploaded_file is None:
            raise ValueError("No file uploaded.")

        filename = getattr(
            uploaded_file, "name", None
        )

        if not filename:
            raise ValueError("Uploaded file has no filename.")

        extension = Path(str(filename)).suffix.lower()

        if extension not in {".csv", ".xlsx"}:
            raise ValueError(
                "Only CSV and XLSX files are supported."
            )

        # Works with Streamlit UploadedFile
        # and FastAPI BytesIO streams.
        if hasattr(uploaded_file, "getvalue"):
            content = uploaded_file.getvalue()
        else:
            uploaded_file.seek(0)
            content = uploaded_file.read()

        if not content:
            raise ValueError("Uploaded file is empty.")

        buffer = BytesIO(content)

        if extension == ".csv":
            try:
                df = pd.read_csv(
                    buffer,
                    encoding="utf-8-sig"
                )
            except UnicodeDecodeError:
                buffer.seek(0)
                df = pd.read_csv(
                    buffer,
                    encoding="cp1252"
                )

        else:
            df = pd.read_excel(
                buffer,
                engine="openpyxl"
            )

        if df.empty:
            raise ValueError(
                "Uploaded file contains no data rows."
            )

        # Normalize column names without
        # changing the actual data values.
        cleaned_columns = []

        for index, column in enumerate(df.columns):
            name = str(column).strip().replace(" ", "_")

            if not name or name.lower().startswith("unnamed:"):
                name = f"Column_{index + 1}"

            cleaned_columns.append(name)

        if len(cleaned_columns) != len(set(cleaned_columns)):
            raise ValueError(
                "Duplicate column names detected after cleaning. "
                "Please rename the duplicate columns."
            )

        df.columns = cleaned_columns

        self.reload_database(df)

        return df.copy()

    # --------------------------------
    # SYNCHRONIZE DATAFRAME WITH DUCKDB
    # --------------------------------

    def reload_database(self, df):

        if df is None:
            raise ValueError("No dataframe provided.")

        if not isinstance(df, pd.DataFrame):
            raise TypeError(
                "Expected a pandas DataFrame."
            )

        if len(df.columns) == 0:
            raise ValueError(
                "Dataframe must contain at least one column."
            )

        updated_df = df.copy().reset_index(drop=True)

        temporary_name = "_datapilot_temp"

        try:
            self.connection.register(
                temporary_name,
                updated_df
            )

            # Replace database contents atomically.
            self.connection.execute("BEGIN TRANSACTION")

            try:
                self.connection.execute(
                    f"""
                    CREATE OR REPLACE TABLE {TABLE_NAME}
                    AS
                    SELECT *
                    FROM {temporary_name}
                    """
                )

                self.connection.execute("COMMIT")

            except Exception:
                self.connection.execute("ROLLBACK")
                raise

            # Update in-memory dataframe only after
            # DuckDB has successfully committed.
            self.current_df = updated_df

            return True

        finally:
            try:
                self.connection.unregister(temporary_name)
            except Exception:
                pass

    # --------------------------------
    # DATABASE SCHEMA
    # --------------------------------

    def get_schema(self):

        schema = self.connection.execute(
            f"DESCRIBE {TABLE_NAME}"
        ).fetchdf()

        columns = []

        for _, row in schema.iterrows():
            columns.append(
                f"{row['column_name']} {row['column_type']}"
            )

        return ", ".join(columns)

    # --------------------------------
    # QUERY EXECUTION
    # --------------------------------

    def execute_query(self, sql):

        if not isinstance(sql, str) or not sql.strip():
            raise ValueError("SQL query is required.")

        # This method is for trusted application SQL.
        # User/AI-generated SQL must go through the
        # separately hardened query execution layer.
        return self.connection.execute(
            sql
        ).fetchdf()

    # --------------------------------
    # DATA PREVIEW
    # --------------------------------

    def preview(self, limit=10):

        limit = int(limit)

        if limit < 1 or limit > 1000:
            raise ValueError(
                "Preview limit must be between 1 and 1000."
            )

        return self.connection.execute(
            f"""
            SELECT *
            FROM {TABLE_NAME}
            LIMIT ?
            """,
            [limit]
        ).fetchdf()

    # --------------------------------
    # CURRENT DATAFRAME
    # --------------------------------

    def get_dataframe(self):

        if self.current_df is None:
            raise ValueError("No dataset loaded.")

        return self.current_df.copy()

    # --------------------------------
    # CLOSE DATABASE
    # --------------------------------

    def close(self):
        self.connection.close()
        self.current_df = None
