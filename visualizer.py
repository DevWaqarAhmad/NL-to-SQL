import plotly.express as px


class Visualizer:


    def create_chart(self, df):


        if df.empty:
            return None


        columns = df.columns.tolist()


        # Category + Number column

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



        # Single numeric column

        for col in columns:


            if (
                df[col]
                .dtype
                != "object"
            ):


                fig = px.histogram(
                    df,
                    x=col,
                    title="Distribution"
                )

                return fig



        return None