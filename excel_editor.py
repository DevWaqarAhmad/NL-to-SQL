import pandas as pd
from io import BytesIO


class ExcelEditor:


    def execute_action(
        self,
        df,
        action
    ):

        if df is None:

            raise Exception(
                "No data loaded."
            )


        df = df.copy()


        action_type = action.get(
            "action"
        )


        # =========================
        # DELETE ROWS
        # =========================

        if action_type == "delete":


            column = action.get(
                "column"
            )

            value = action.get(
                "value"
            )


            self.validate_column(
                df,
                column
            )


            df = df[
                df[column]
                .astype(str)
                .str.lower()
                != str(value).lower()
            ]


            return df.reset_index(
                drop=True
            )



        # =========================
        # UPDATE VALUES
        # =========================

        elif action_type == "update":


            column = action.get(
                "column"
            )

            old_value = action.get(
                "old_value"
            )

            new_value = action.get(
                "new_value"
            )


            self.validate_column(
                df,
                column
            )


            df[column] = (

                df[column]
                .astype(str)
                .replace(
                    str(old_value),
                    str(new_value)
                )

            )


            return df



        # =========================
        # ADD ROW
        # =========================

        elif action_type == "add":


            data = action.get(
                "data"
            )


            if not data:

                raise Exception(
                    "No row data provided."
                )


            new_row = pd.DataFrame(
                [data]
            )


            return pd.concat(
                [
                    df,
                    new_row
                ],
                ignore_index=True
            )



        # =========================
        # REMOVE DUPLICATES
        # =========================

        elif action_type == "remove_duplicates":


            return (
                df
                .drop_duplicates()
                .reset_index(
                    drop=True
                )
            )



        else:

            raise Exception(
                f"Unsupported action: {action_type}"
            )



    # =========================
    # COLUMN VALIDATION
    # =========================

    def validate_column(
        self,
        df,
        column
    ):


        if column not in df.columns:

            raise Exception(
                f"Column '{column}' not found."
            )



    # =========================
    # MANUAL ADD
    # =========================

    def add_row(
        self,
        df,
        data
    ):

        return self.execute_action(
            df,
            {
                "action":"add",
                "data":data
            }
        )



    # =========================
    # MANUAL UPDATE
    # =========================

    def update_row(
        self,
        df,
        index,
        data
    ):


        df = df.copy()


        for key,value in data.items():

            if key in df.columns:

                df.loc[index,key] = value


        return df



    # =========================
    # MANUAL DELETE
    # =========================

    def delete_row(
        self,
        df,
        index
    ):


        df = df.copy()


        df = df.drop(
            index=index
        )


        return df.reset_index(
            drop=True
        )



    # =========================
    # EXPORT EXCEL
    # =========================

    def export_excel(
        self,
        df
    ):


        output = BytesIO()


        df.to_excel(
            output,
            index=False,
            engine="openpyxl"
        )


        output.seek(0)


        return output