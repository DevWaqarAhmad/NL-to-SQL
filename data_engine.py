import duckdb
import pandas as pd
from io import BytesIO


TABLE_NAME = "uploaded_data"


class DataEngine:


    def __init__(self):

        self.connection = duckdb.connect(
            database=":memory:"
        )


    def load_file(self, uploaded_file):

        if uploaded_file is None:
            raise ValueError(
                "No file uploaded."
            )


        file_name = uploaded_file.name.lower()

        file_buffer = BytesIO(
            uploaded_file.getvalue()
        )


        if file_name.endswith(".csv"):

            df = pd.read_csv(
                file_buffer
            )


        elif file_name.endswith(".xlsx"):

            df = pd.read_excel(
                file_buffer,
                engine="openpyxl"
            )


        else:

            raise ValueError(
                "Only CSV and XLSX files supported."
            )


        if df.empty:

            raise ValueError(
                "File is empty."
            )


        # Clean column names

        df.columns = [
            str(col)
            .strip()
            .replace(" ", "_")
            for col in df.columns
        ]


        self.connection.register(
            "temp_df",
            df
        )


        self.connection.execute(
            f"""
            CREATE OR REPLACE TABLE {TABLE_NAME}
            AS
            SELECT *
            FROM temp_df
            """
        )


        return df



    def get_schema(self):

        schema_df = self.connection.execute(
            f"DESCRIBE {TABLE_NAME}"
        ).fetchdf()


        columns = []


        for _, row in schema_df.iterrows():

            columns.append(
                f"{row['column_name']} {row['column_type']}"
            )


        return ", ".join(columns)



    def execute_query(self, sql):

        result = self.connection.execute(
            sql
        ).fetchdf()


        return result



    def preview(self, limit=10):

        return self.connection.execute(
            f"""
            SELECT *
            FROM {TABLE_NAME}
            LIMIT {limit}
            """
        ).fetchdf()