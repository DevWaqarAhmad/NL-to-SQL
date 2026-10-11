import duckdb
import pandas as pd

from io import BytesIO


TABLE_NAME = "uploaded_data"



class DataEngine:


    def __init__(self):

        self.connection = duckdb.connect(
            database=":memory:"
        )

        self.current_df = None



    # -------------------------------
    # LOAD CSV / EXCEL
    # -------------------------------

    def load_file(
        self,
        uploaded_file
    ):


        if uploaded_file is None:

            raise ValueError(
                "No file uploaded."
            )


        file_name = uploaded_file.name.lower()


        buffer = BytesIO(
            uploaded_file.getvalue()
        )


        if file_name.endswith(".csv"):


            df = pd.read_csv(
                buffer
            )


        elif file_name.endswith(".xlsx"):


            df = pd.read_excel(
                buffer,
                engine="openpyxl"
            )


        else:

            raise ValueError(
                "Only CSV and XLSX files are supported."
            )



        if df.empty:

            raise ValueError(
                "Uploaded file is empty."
            )



        df.columns = [

            str(col)
            .strip()
            .replace(
                " ",
                "_"
            )

            for col in df.columns

        ]


        self.reload_database(
            df
        )


        return df



    # -------------------------------
    # UPDATE DATABASE
    # -------------------------------

    def reload_database(
        self,
        df
    ):


        if df is None or df.empty:

            raise ValueError(
                "Data cannot be empty."
            )


        self.current_df = df.copy()



        self.connection.register(
            "temp_df",
            self.current_df
        )


        self.connection.execute(

            f"""

            CREATE OR REPLACE TABLE {TABLE_NAME}

            AS

            SELECT *

            FROM temp_df

            """

        )


        return True



    # -------------------------------
    # SCHEMA
    # -------------------------------

    def get_schema(
        self
    ):


        schema = self.connection.execute(

            f"DESCRIBE {TABLE_NAME}"

        ).fetchdf()



        columns = []


        for _, row in schema.iterrows():


            columns.append(

                f"{row['column_name']} {row['column_type']}"

            )


        return ", ".join(columns)



    # -------------------------------
    # QUERY EXECUTION
    # -------------------------------

    def execute_query(
        self,
        sql
    ):


        return self.connection.execute(
            sql
        ).fetchdf()



    # -------------------------------
    # PREVIEW
    # -------------------------------

    def preview(
        self,
        limit=10
    ):


        return self.connection.execute(

            f"""

            SELECT *

            FROM {TABLE_NAME}

            LIMIT {limit}

            """

        ).fetchdf()



    # -------------------------------
    # CURRENT DATA
    # -------------------------------

    def get_dataframe(
        self
    ):

        return self.current_df.copy()