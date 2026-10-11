import plotly.express as px


class Visualizer:


    def create_chart(self, df):


        if df is None or df.empty:
            return None



        columns = df.columns.tolist()



        # --------------------------------
        # Single value result
        # --------------------------------

        if (
            len(df) == 1
            and len(columns) == 1
        ):

            return None



        # --------------------------------
        # Category + Numeric
        # Example:
        # Brand | Count
        # Ford  | 120
        # --------------------------------

        if len(columns) >= 2:


            first = columns[0]
            second = columns[1]


            if (
                df[second]
                .dtype
                != "object"
            ):


                fig = px.bar(
                    df,
                    x=first,
                    y=second,
                    title="Data Analysis"
                )


                return fig



        # --------------------------------
        # Category only
        # Example:
        # Ford
        # Toyota
        # BMW
        #
        # Convert into counts
        # --------------------------------


        if len(columns) == 1:


            col = columns[0]


            counts = (
                df[col]
                .value_counts()
                .reset_index()
            )


            counts.columns = [
                col,
                "Count"
            ]



            # Bar chart

            fig = px.bar(
                counts,
                x=col,
                y="Count",
                title=f"{col} Distribution"
            )


            return fig



        # --------------------------------
        # Numeric columns
        # --------------------------------

        for col in columns:


            if (
                df[col]
                .dtype
                != "object"
            ):


                fig = px.histogram(
                    df,
                    x=col,
                    title="Numeric Distribution"
                )


                return fig



        return None