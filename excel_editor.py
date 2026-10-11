import pandas as pd
from io import BytesIO


class ExcelEditor:


    def add_row(self, df, data):

        new_row = pd.DataFrame(
            [data]
        )

        updated_df = pd.concat(
            [
                df,
                new_row
            ],
            ignore_index=True
        )

        return updated_df



    def update_row(self, df, index, data):

        for key, value in data.items():

            df.loc[index, key] = value


        return df



    def delete_row(self, df, index):

        df = df.drop(
            index=index
        )

        df = df.reset_index(
            drop=True
        )

        return df



    def export_excel(self, df):

        output = BytesIO()

        df.to_excel(
            output,
            index=False,
            engine="openpyxl"
        )

        output.seek(0)

        return output