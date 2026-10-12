from io import BytesIO
import math

import pandas as pd
from pandas.api import types as ptypes


class ExcelEditor:
    """Apply one validated, tabular edit to a copy of a DataFrame."""

    SUPPORTED_OPERATORS = {
        "eq", "ne", "gt", "gte", "lt", "lte",
        "in", "contains", "is_null", "not_null",
    }

    def validate_column(self, df, column):
        if not isinstance(column, str) or column not in df.columns:
            raise ValueError(f"Column '{column}' not found.")

    def convert_value(self, series, value):
        """Convert to the existing column type; never stringify numeric columns."""
        if value is None or value is pd.NA:
            return None
        dtype = series.dtype

        if ptypes.is_bool_dtype(dtype):
            if isinstance(value, bool):
                return value
            value_text = str(value).strip().lower()
            if value_text in ("true", "yes", "1"):
                return True
            if value_text in ("false", "no", "0"):
                return False
            raise ValueError("Invalid boolean value.")

        if ptypes.is_integer_dtype(dtype):
            if isinstance(value, bool):
                raise ValueError("Boolean is not a valid integer.")
            try:
                number = pd.to_numeric(pd.Series([value]), errors="raise").iloc[0]
                if not math.isfinite(float(number)) or not float(number).is_integer():
                    raise ValueError("Expected a finite whole number.")
                integer = int(number)
                # Try a scalar assignment using the original dtype, for range checks.
                pd.Series([integer], dtype=dtype)
                return integer
            except (TypeError, OverflowError, ValueError) as exc:
                raise ValueError(f"Invalid integer value: {value!r}") from exc

        if ptypes.is_float_dtype(dtype):
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value: {value!r}") from exc
            if not math.isfinite(number):
                raise ValueError("Numeric value must be finite.")
            return number

        if ptypes.is_datetime64_any_dtype(dtype):
            try:
                return pd.to_datetime(value, errors="raise")
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid date/time: {value!r}") from exc

        if ptypes.is_categorical_dtype(dtype):
            text = str(value)
            if text not in series.cat.categories:
                raise ValueError(f"Value {text!r} is not an existing category.")
            return text

        return str(value)

    def _nullable_column(self, df, column):
        """Allow missing values without converting numeric data to text."""
        dtype = df[column].dtype
        if ptypes.is_integer_dtype(dtype):
            if not ptypes.is_extension_array_dtype(dtype):
                df[column] = df[column].astype("Int64")
        elif ptypes.is_bool_dtype(dtype):
            if not ptypes.is_extension_array_dtype(dtype):
                df[column] = df[column].astype("boolean")
        elif ptypes.is_string_dtype(dtype) and not ptypes.is_object_dtype(dtype):
            pass  # pandas StringDtype already supports missing values
        return df

    def make_condition_mask(self, df, condition):
        if not isinstance(condition, dict):
            raise ValueError("Invalid filter condition.")
        column = condition.get("column")
        operator = condition.get("operator", "eq")
        self.validate_column(df, column)
        if operator not in self.SUPPORTED_OPERATORS:
            raise ValueError(f"Unsupported operator: {operator}")

        series = df[column]
        value = condition.get("value")
        if operator == "is_null":
            return series.isna()
        if operator == "not_null":
            return series.notna()
        if operator == "contains":
            if value is None:
                raise ValueError("Contains requires a value.")
            return series.astype("string").str.contains(
                str(value), case=False, regex=False, na=False
            ).fillna(False)
        if operator == "in":
            if not isinstance(value, list) or not value:
                raise ValueError("'in' requires a non-empty list.")
            mask = pd.Series(False, index=df.index)
            for item in value:
                mask |= self.make_condition_mask(df, {
                    "column": column, "operator": "eq", "value": item
                })
            return mask
        if value is None:
            if operator == "eq":
                return series.isna()
            if operator == "ne":
                return series.notna()
            raise ValueError("Cannot order-compare against null.")

        converted = self.convert_value(series, value)
        if operator in ("eq", "ne"):
            if ptypes.is_object_dtype(series.dtype) or ptypes.is_string_dtype(series.dtype):
                equal = (series.astype("string").str.casefold() == str(converted).casefold()).fillna(False)
            else:
                equal = (series == converted).fillna(False)
            return equal if operator == "eq" else (~equal & series.notna()).fillna(False)

        if not (ptypes.is_numeric_dtype(series.dtype) or ptypes.is_datetime64_any_dtype(series.dtype)):
            raise ValueError(f"Operator '{operator}' needs numeric or datetime data.")
        comparisons = {
            "gt": lambda: series > converted,
            "gte": lambda: series >= converted,
            "lt": lambda: series < converted,
            "lte": lambda: series <= converted,
        }
        return comparisons[operator]().fillna(False)

    def get_filter_mask(self, df, action):
        conditions = action.get("conditions")
        if conditions is None:
            column = action.get("column")
            key = "value" if action.get("action") == "delete" else "old_value"
            if column is None or key not in action:
                raise ValueError("Filter conditions are required.")
            conditions = [{"column": column, "operator": "eq", "value": action[key]}]
        if not isinstance(conditions, list) or not 1 <= len(conditions) <= 10:
            raise ValueError("Provide between 1 and 10 filter conditions.")
        mask = pd.Series(True, index=df.index)
        for condition in conditions:
            mask &= self.make_condition_mask(df, condition)
        return mask.fillna(False)

    def execute_action(self, df, action):
        if df is None:
            raise ValueError("No data loaded.")
        if not isinstance(action, dict):
            raise ValueError("Action must be a JSON object.")
        result = df.copy().reset_index(drop=True)
        kind = action.get("action")

        if kind == "delete":
            mask = self.get_filter_mask(result, action)
            if not mask.any():
                raise ValueError("No matching records found.")
            return result.loc[~mask].reset_index(drop=True)

        if kind == "update":
            column = action.get("column")
            self.validate_column(result, column)
            if "new_value" not in action and "value" not in action:
                raise ValueError("New value is required.")
            value = action["new_value"] if "new_value" in action else action["value"]
            mask = self.get_filter_mask(result, action)
            if not mask.any():
                raise ValueError("No matching records found.")
            converted = self.convert_value(result[column], value)
            if converted is None:
                self._nullable_column(result, column)
                converted = pd.NA if (ptypes.is_integer_dtype(result[column].dtype) or ptypes.is_bool_dtype(result[column].dtype)) else None
            result.loc[mask, column] = converted
            return result

        if kind == "add":
            data = action.get("data")
            if not isinstance(data, dict) or not data:
                raise ValueError("Row data is required.")
            unknown = set(data) - set(result.columns)
            if unknown:
                raise ValueError(f"Unknown columns: {sorted(unknown)}")
            row = {}
            for column in result.columns:
                value = self.convert_value(result[column], data[column]) if column in data else None
                if value is None:
                    self._nullable_column(result, column)
                    dtype = result[column].dtype
                    value = pd.NA if (ptypes.is_integer_dtype(dtype) or ptypes.is_bool_dtype(dtype) or (ptypes.is_string_dtype(dtype) and not ptypes.is_object_dtype(dtype))) else None
                row[column] = value
            # Construct using existing dtypes, including nullable Int64/boolean.
            addition = pd.DataFrame([row], columns=result.columns)
            for column in result.columns:
                addition[column] = addition[column].astype(result[column].dtype)
            return pd.concat([result, addition], ignore_index=True)

        if kind == "remove_duplicates":
            return result.drop_duplicates().reset_index(drop=True)
        raise ValueError(f"Unsupported action: {kind}")

    def add_row(self, df, data):
        return self.execute_action(df, {"action": "add", "data": data})

    def update_row(self, df, index, data):
        if index not in df.index:
            raise ValueError("Row index not found.")
        result = df.copy()
        for column, value in data.items():
            self.validate_column(result, column)
            converted = self.convert_value(result[column], value)
            if converted is None:
                self._nullable_column(result, column)
                converted = pd.NA if (ptypes.is_integer_dtype(result[column].dtype) or ptypes.is_bool_dtype(result[column].dtype)) else None
            result.loc[index, column] = converted
        return result

    def delete_row(self, df, index):
        if index not in df.index:
            raise ValueError("Row index not found.")
        return df.drop(index=index).reset_index(drop=True)

    def export_excel(self, df):
        output = BytesIO()
        df.to_excel(output, index=False, engine="openpyxl")
        output.seek(0)
        return output
