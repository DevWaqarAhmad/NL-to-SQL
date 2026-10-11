import plotly.express as px
import pandas as pd



class Visualizer:


    def create_chart(
        self,
        df
    ):


        if df is None or df.empty:

            return None



        try:

            columns = df.columns.tolist()



            # -------------------------
            # Single value result
            # Example:
            # Total Sales = 5000
            # -------------------------

            if (
                len(df) == 1
                and len(columns) == 1
            ):

                return None



            # -------------------------
            # Category + Numeric
            # -------------------------

            if len(columns) >= 2:


                first = columns[0]
                second = columns[1]


                if pd.api.types.is_numeric_dtype(
                    df[second]
                ):


                    return px.bar(
                        df,
                        x=first,
                        y=second,
                        title="Data Analysis"
                    )



            # -------------------------
            # Single column
            # Category distribution
            # -------------------------

            if len(columns) == 1:


                col = columns[0]


                counts = (

                    df[col]
                    .value_counts()
                    .head(15)
                    .reset_index()

                )


                counts.columns = [
                    col,
                    "Count"
                ]


                return px.bar(
                    counts,
                    x=col,
                    y="Count",
                    title=f"{col} Distribution"
                )



            # -------------------------
            # Numeric columns
            # -------------------------

            for col in columns:


                if pd.api.types.is_numeric_dtype(
                    df[col]
                ):


                    return px.histogram(
                        df,
                        x=col,
                        title=f"{col} Distribution"
                    )



            # -------------------------
            # Date column
            # -------------------------

            for col in columns:


                if pd.api.types.is_datetime64_any_dtype(
                    df[col]
                ):


                    return px.line(
                        df,
                        x=col,
                        title=f"{col} Trend"
                    )


            return None



        except Exception:

            return None