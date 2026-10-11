import pandas as pd
from io import BytesIO



class ExcelEditor:



    def execute_action(
        self,
        df,
        action
    ):

        action_type = action.get(
            "action"
        )


        # -------------------------
        # DELETE DATA
        # -------------------------

        if action_type == "delete":


            column = action.get(
                "column"
            )

            value = action.get(
                "value"
            )


            if column not in df.columns:

                raise Exception(
                    f"Column '{column}' not found"
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



        # -------------------------
        # UPDATE DATA
        # -------------------------

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


            if column not in df.columns:

                raise Exception(
                    f"Column '{column}' not found"
                )


            df[column] = (
                df[column]
                .replace(
                    old_value,
                    new_value
                )
            )


            return df



        # -------------------------
        # ADD NEW ROW
        # -------------------------

        elif action_type == "add":


            data = action.get(
                "data"
            )


            if not data:

                raise Exception(
                    "No data provided"
                )


            new_row = pd.DataFrame(
                [data]
            )


            df = pd.concat(
                [
                    df,
                    new_row
                ],
                ignore_index=True
            )


            return df



        # -------------------------
        # REMOVE DUPLICATES
        # -------------------------

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
                f"Unknown action: {action_type}"
            )



    # -------------------------
    # OLD FUNCTIONS KEEP
    # -------------------------

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



    def update_row(
        self,
        df,
        index,
        data
    ):


        for key,value in data.items():

            df.loc[index,key] = value


        return df



    def delete_row(
        self,
        df,
        index
    ):


        df = df.drop(
            index=index
        )


        return df.reset_index(
            drop=True
        )



    # -------------------------
    # EXPORT FILE
    # -------------------------

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