
from io import BytesIO

import pandas as pd


class ExcelEditor:

    SUPPORTED_OPERATORS = {
        "eq", "ne", "gt", "gte", "lt", "lte",
        "in", "contains", "is_null", "not_null"
    }

    def validate_column(self, df, column):
        if column not in df.columns:
            raise ValueError(
                f"Column '{column}' not found."
            )

    def convert_value(self, series, value):
        """Convert a proposed value to the column's existing type."""

        if value is None:
            return None

        if pd.api.types.is_bool_dtype(series.dtype):
            if isinstance(value, bool):
                return value

            if str(value).lower() in ("true", "1", "yes"):
                return True

            if str(value).lower() in ("false", "0", "no"):
                return False

            raise ValueError("Invalid boolean value.")

        if pd.api.types.is_numeric_dtype(series.dtype):
            number = pd.to_numeric(
                pd.Series([value]),
                errors="raise"
            ).iloc[0]

            if pd.api.types.is_integer_dtype(series.dtype):
                if not float(number).is_integer():
                    raise ValueError(
                        "Cannot put a decimal in an integer column."
                    )
                return int(number)

            return float(number)

        if pd.api.types.is_datetime64_any_dtype(series.dtype):
            return pd.to_datetime(value, errors="raise")

        return str(value)

    def make_condition_mask(self, df, condition):
        if not isinstance(condition, dict):
            raise ValueError("Invalid filter condition.")

        column = condition.get("column")
        operator = condition.get("operator", "eq")
        value = condition.get("value")

        self.validate_column(df, column)

        if operator not in self.SUPPORTED_OPERATORS:
            raise ValueError(
                f"Unsupported operator: {operator}"
            )

        series = df[column]

        if operator == "is_null":
            return series.isna()

        if operator == "not_null":
            return series.notna()

        if operator == "contains":
            if value is None:
                raise ValueError("Contains requires a value.")

            return (
                series.astype("string")
                .str.contains(
                    str(value),
                    case=False,
                    regex=False,
                    na=False
                )
            )

        if operator == "in":
            if not isinstance(value, list) or not value:
                raise ValueError(
                    "'in' requires a non-empty list."
                )

            mask = pd.Series(False, index=df.index)

            for item in value:
                mask |= self.make_condition_mask(
                    df,
                    {
                        "column": column,
                        "operator": "eq",
                        "value": item
                    }
                )

            return mask

        if value is None:
            if operator == "eq":
                return series.isna()
            if operator == "ne":
                return series.notna()
            raise ValueError(
                "Comparison with null is not supported."
            )

        converted = self.convert_value(series, value)

        if operator in ("eq", "ne"):
            if (
                pd.api.types.is_object_dtype(series.dtype)
                or pd.api.types.is_string_dtype(series.dtype)
            ):
                equal = (
                    series.astype("string").str.casefold()
                    == str(converted).casefold()
                ).fillna(False)
            else:
                equal = (series == converted).fillna(False)

            if operator == "eq":
                return equal

            return (~equal) & series.notna()

        if (
            not pd.api.types.is_numeric_dtype(series.dtype)
            and not pd.api.types.is_datetime64_any_dtype(
                series.dtype
            )
        ):
            raise ValueError(
                f"Operator '{operator}' requires a "
                "numeric or datetime column."
            )

        if operator == "gt":
            mask = series > converted
        elif operator == "gte":
            mask = series >= converted
        elif operator == "lt":
            mask = series < converted
        else:
            mask = series <= converted

        return mask.fillna(False)

    def get_filter_mask(self, df, action):
        """
        Supported:
        conditions: [{column, operator, value}]
        Legacy:
        column + value / old_value
        """

        conditions = action.get("conditions")

        if conditions is None:
            column = action.get("column")

            if action.get("action") == "delete":
                value = action.get("value")
            else:
                value = action.get("old_value")

            if column is None or value is None:
                raise ValueError(
                    "Filter conditions are required."
                )

            conditions = [
                {
                    "column": column,
                    "operator": "eq",
                    "value": value
                }
            ]

        if not isinstance(conditions, list) or not conditions:
            raise ValueError(
                "Conditions must be a non-empty list."
            )

        if len(conditions) > 10:
            raise ValueError(
                "Maximum 10 conditions are supported."
            )

        mask = pd.Series(True, index=df.index)

        # All conditions must match (AND).
        for condition in conditions:
            mask &= self.make_condition_mask(df, condition)

        return mask.fillna(False)

    def execute_action(self, df, action):
        if df is None:
            raise ValueError("No data loaded.")

        if not isinstance(action, dict):
            raise ValueError("Action must be a JSON object.")

        df = df.copy()
        action_type = action.get("action")

        # DELETE
        if action_type == "delete":
            mask = self.get_filter_mask(df, action)

            if not mask.any():
                raise ValueError("No matching records found.")

            return df.loc[~mask].reset_index(drop=True)

        # UPDATE
        if action_type == "update":
            column = action.get("column")
            self.validate_column(df, column)

            if "new_value" not in action and "value" not in action:
                raise ValueError("New value is required.")

            new_value = action.get(
                "new_value",
                action.get("value")
            )

            mask = self.get_filter_mask(df, action)

            if not mask.any():
                raise ValueError("No matching records found.")

            converted = self.convert_value(
                df[column],
                new_value
            )

            if converted is None:
                if (
                    not pd.api.types.is_object_dtype(
                        df[column].dtype
                    )
                    and not pd.api.types.is_extension_array_dtype(
                        df[column].dtype
                    )
                ):
                    raise ValueError(
                        "This column cannot safely store null."
                    )

            # Assign directly without converting
            # the whole column to strings.
            df.loc[mask, column] = converted

            return df

        # ADD
        if action_type == "add":
            data = action.get("data")

            if not isinstance(data, dict) or not data:
                raise ValueError("Row data is required.")

            unknown = set(data) - set(df.columns)

            if unknown:
                raise ValueError(
                    f"Unknown columns: {sorted(unknown)}"
                )

            row = {}

            for column in df.columns:
                if column in data:
                    row[column] = self.convert_value(
                        df[column],
                        data[column]
                    )
                else:
                    row[column] = None

            new_row = pd.DataFrame([row])

            result = pd.concat(
                [df, new_row],
                ignore_index=True
            )

            # Restore original numeric and datetime types
            # when possible.
            for column in df.columns:
                original_dtype = df[column].dtype

                try:
                    result[column] = result[column].astype(
                        original_dtype
                    )
                except (ValueError, TypeError):
                    if pd.api.types.is_integer_dtype(
                        original_dtype
                    ):
                        result[column] = (
                            pd.to_numeric(
                                result[column],
                                errors="raise"
                            ).astype("Int64")
                        )

            return result

        # REMOVE DUPLICATES
        if action_type == "remove_duplicates":
            return df.drop_duplicates().reset_index(drop=True)

        raise ValueError(
            f"Unsupported action: {action_type}"
        )

    def add_row(self, df, data):
        return self.execute_action(
            df,
            {"action": "add", "data": data}
        )

    def update_row(self, df, index, data):
        df = df.copy()

        if index not in df.index:
            raise ValueError("Row index not found.")

        for column, value in data.items():
            self.validate_column(df, column)
            df.loc[index, column] = self.convert_value(
                df[column],
                value
            )

        return df

    def delete_row(self, df, index):
        if index not in df.index:
            raise ValueError("Row index not found.")

        return (
            df.drop(index=index)
            .reset_index(drop=True)
        )

    def export_excel(self, df):
        output = BytesIO()

        df.to_excel(
            output,
            index=False,
            engine="openpyxl"
        )

        output.seek(0)
        return output
