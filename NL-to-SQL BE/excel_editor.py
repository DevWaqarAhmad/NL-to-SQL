from io import BytesIO
import math
import pandas as pd
from pandas.api import types as ptypes
class ExcelEditor:
    """
    DataPilot AI — Excel and CSV Editing Engine.
    Applies validated editing actions to copies
    of pandas DataFrames.
    Supported actions:
        add
        add_rows
        update
        delete
        remove_duplicates
    The engine does not generate AI responses,
    translate data, or modify original DataFrames.
    """
    SUPPORTED_ACTIONS = {
        "add",
        "add_rows",
        "update",
        "delete",
        "remove_duplicates",
    }
    SUPPORTED_OPERATORS = {
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "contains",
        "is_null",
        "not_null",
    }
    # =====================================
    # COLUMN VALIDATION
    # =====================================
    def validate_column(self, df, column):
        if (
            not isinstance(column, str)
            or column not in df.columns
        ):
            raise ValueError(
                f"Column '{column}' not found."
            )
    # =====================================
    # VALUE CONVERSION
    # =====================================
    def convert_value(self, series, value):
        """
        Convert a supplied value to the existing
        column's data type.
        Never translate original dataset values
        or stringify numeric columns.
        """
        if value is None or value is pd.NA:
            return None
        dtype = series.dtype
        # Boolean columns
        if ptypes.is_bool_dtype(dtype):
            if isinstance(value, bool):
                return value
            value_text = str(value).strip().lower()
            if value_text in ("true", "yes", "1"):
                return True
            if value_text in ("false", "no", "0"):
                return False
            raise ValueError(
                "Invalid boolean value."
            )
        # Integer columns
        if ptypes.is_integer_dtype(dtype):
            if isinstance(value, bool):
                raise ValueError(
                    "Boolean is not a valid integer."
                )
            try:
                number = pd.to_numeric(
                    pd.Series([value]),
                    errors="raise",
                ).iloc[0]
                if (
                    not math.isfinite(float(number))
                    or not float(number).is_integer()
                ):
                    raise ValueError(
                        "Expected a finite whole number."
                    )
                integer = int(number)
                # Check compatibility and integer range.
                pd.Series(
                    [integer],
                    dtype=dtype,
                )
                return integer
            except (
                TypeError,
                OverflowError,
                ValueError,
            ) as exc:
                raise ValueError(
                    f"Invalid integer value: {value!r}"
                ) from exc
        # Floating-point columns
        if ptypes.is_float_dtype(dtype):
            if isinstance(value, bool):
                raise ValueError(
                    "Boolean is not a valid numeric value."
                )
            try:
                number = float(value)
            except (
                TypeError,
                ValueError,
                OverflowError,
            ) as exc:
                raise ValueError(
                    f"Invalid numeric value: {value!r}"
                ) from exc
            if not math.isfinite(number):
                raise ValueError(
                    "Numeric value must be finite."
                )
            return number
        # Date/time columns
        if ptypes.is_datetime64_any_dtype(dtype):
            try:
                return pd.to_datetime(
                    value,
                    errors="raise",
                )
            except (
                TypeError,
                ValueError,
                OverflowError,
            ) as exc:
                raise ValueError(
                    f"Invalid date/time: {value!r}"
                ) from exc
        # Categorical columns
        if isinstance(dtype, pd.CategoricalDtype):
            text = str(value)
            if text not in series.cat.categories:
                raise ValueError(
                    f"Value {text!r} is not "
                    "an existing category."
                )
            return text
        # String/object columns
        return str(value)
    # =====================================
    # NULLABLE COLUMN SUPPORT
    # =====================================
    def _nullable_column(self, df, column):
        """
        Allow missing values while preserving
        numeric and boolean data types.
        """
        dtype = df[column].dtype
        if ptypes.is_integer_dtype(dtype):
            if not isinstance(
                dtype,
                pd.api.extensions.ExtensionDtype,
            ):
                df[column] = df[column].astype(
                    "Int64"
                )
        elif ptypes.is_bool_dtype(dtype):
            if not isinstance(
                dtype,
                pd.api.extensions.ExtensionDtype,
            ):
                df[column] = df[column].astype(
                    "boolean"
                )
        return df
    # =====================================
    # SINGLE FILTER CONDITION
    # =====================================
    def make_condition_mask(
        self,
        df,
        condition,
    ):
        """
        Build a boolean mask for one condition.
        Dataset values and column names are
        compared without language translation.
        """
        if not isinstance(condition, dict):
            raise ValueError(
                "Invalid filter condition."
            )
        column = condition.get("column")
        operator = condition.get("operator", "eq")
        self.validate_column(df, column)
        if operator not in self.SUPPORTED_OPERATORS:
            raise ValueError(
                f"Unsupported operator: {operator}"
            )
        series = df[column]
        value = condition.get("value")
        # Missing values
        if operator == "is_null":
            return series.isna()
        if operator == "not_null":
            return series.notna()
        # Case-insensitive substring matching
        if operator == "contains":
            if value is None:
                raise ValueError(
                    "Contains requires a value."
                )
            return (
                series.astype("string")
                .str.contains(
                    str(value),
                    case=False,
                    regex=False,
                    na=False,
                )
                .fillna(False)
            )
        # Membership in a list
        if operator == "in":
            if (
                not isinstance(value, list)
                or not value
            ):
                raise ValueError(
                    "'in' requires a non-empty list."
                )
            mask = pd.Series(
                False,
                index=df.index,
                dtype=bool,
            )
            for item in value:
                if isinstance(item, (list, dict)):
                    raise ValueError(
                        "IN values must be scalar."
                    )
                item_mask = self.make_condition_mask(
                    df,
                    {
                        "column": column,
                        "operator": "eq",
                        "value": item,
                    },
                )
                mask = mask | item_mask.fillna(False)
            return mask.fillna(False)
        # Null comparisons
        if value is None:
            if operator == "eq":
                return series.isna()
            if operator == "ne":
                return series.notna()
            raise ValueError(
                "Cannot order-compare against null."
            )
        converted = self.convert_value(
            series,
            value,
        )
        # Equality / inequality
        if operator in ("eq", "ne"):
            if (
                ptypes.is_object_dtype(series.dtype)
                or ptypes.is_string_dtype(series.dtype)
            ):
                equal = (
                    series.astype("string")
                    .str.casefold()
                    == str(converted).casefold()
                ).fillna(False)
            else:
                equal = (
                    series == converted
                ).fillna(False)
            if operator == "eq":
                return equal
            return (
                ~equal & series.notna()
            ).fillna(False)
        # Ordered comparisons
        if not (
            ptypes.is_numeric_dtype(series.dtype)
            or ptypes.is_datetime64_any_dtype(
                series.dtype
            )
        ):
            raise ValueError(
                f"Operator '{operator}' needs "
                "numeric or datetime data."
            )
        if operator == "gt":
            mask = series > converted
        elif operator == "gte":
            mask = series >= converted
        elif operator == "lt":
            mask = series < converted
        elif operator == "lte":
            mask = series <= converted
        else:
            raise ValueError(
                f"Unsupported operator: {operator}"
            )
        return mask.fillna(False)
    # =====================================
    # COMBINED FILTER CONDITIONS
    # =====================================
    def get_filter_mask(self, df, action):
        """
        Combine conditions using logical AND.
        A minimum of one explicit condition
        is required for update and delete.
        """
        conditions = action.get("conditions")
        # Preserve compatibility with older
        # single-column action formats.
        if conditions is None:
            column = action.get("column")
            key = (
                "value"
                if action.get("action") == "delete"
                else "old_value"
            )
            if column is None or key not in action:
                raise ValueError(
                    "Filter conditions are required."
                )
            conditions = [
                {
                    "column": column,
                    "operator": "eq",
                    "value": action[key],
                }
            ]
        if (
            not isinstance(conditions, list)
            or not 1 <= len(conditions) <= 10
        ):
            raise ValueError(
                "Provide between 1 and 10 "
                "filter conditions."
            )
        mask = pd.Series(
            True,
            index=df.index,
            dtype=bool,
        )
        for condition in conditions:
            condition_mask = (
                self.make_condition_mask(
                    df,
                    condition,
                )
            )
            mask = (
                mask & condition_mask
            ).fillna(False)
        return mask.fillna(False)
    # =====================================
    # EXECUTE EDITING ACTION
    # =====================================
    def execute_action(self, df, action):
        """
        Apply exactly one editing action.
        A new DataFrame is returned.
        The supplied DataFrame is not modified.
        The API's preview/confirmation workflow
        determines whether changes are committed.
        """
        if df is None:
            raise ValueError(
                "No data loaded."
            )
        if not isinstance(df, pd.DataFrame):
            raise ValueError(
                "Expected a pandas DataFrame."
            )
        if not isinstance(action, dict):
            raise ValueError(
                "Action must be a JSON object."
            )
        result = (
            df.copy(deep=True)
            .reset_index(drop=True)
        )
        kind = action.get("action")
        if kind not in self.SUPPORTED_ACTIONS:
            raise ValueError(
                f"Unsupported action: {kind}"
            )
        # =================================
        # DELETE MATCHING ROWS
        # =================================
        if kind == "delete":
            mask = self.get_filter_mask(
                result,
                action,
            )
            if not mask.any():
                raise ValueError(
                    "No matching records found."
                )
            return (
                result.loc[~mask]
                .reset_index(drop=True)
            )
        # =================================
        # UPDATE MATCHING VALUES
        # =================================
        if kind == "update":
            column = action.get("column")
            self.validate_column(
                result,
                column,
            )
            if (
                "new_value" not in action
                and "value" not in action
            ):
                raise ValueError(
                    "New value is required."
                )
            value = (
                action["new_value"]
                if "new_value" in action
                else action["value"]
            )
            mask = self.get_filter_mask(
                result,
                action,
            )
            if not mask.any():
                raise ValueError(
                    "No matching records found."
                )
            converted = self.convert_value(
                result[column],
                value,
            )
            if converted is None:
                self._nullable_column(
                    result,
                    column,
                )
                dtype = result[column].dtype
                converted = (
                    pd.NA
                    if (
                        ptypes.is_integer_dtype(dtype)
                        or ptypes.is_bool_dtype(dtype)
                        or isinstance(
                            dtype,
                            pd.StringDtype,
                        )
                    )
                    else None
                )
            result.loc[
                mask,
                column,
            ] = converted
            return result
        # =================================
        # ADD A NEW ROW
        # =================================
        # =================================
        # ADD MULTIPLE ROWS — ALL OR NOTHING
        # =================================
        if kind == "add_rows":
            # Preserve the existing single-row conversion and
            # dtype behavior by executing the established add path.
            if set(action) != {"action", "rows"}:
                raise ValueError(
                    "add_rows requires only action and rows."
                )
            rows = action.get("rows")
            if not isinstance(rows, list) or not (2 <= len(rows) <= 100):
                raise ValueError(
                    "add_rows requires between 2 and 100 rows."
                )
            # 'result' is already a deep copy; any failure prevents
            # a partial batch from being returned or committed.
            for number, row in enumerate(rows, start=1):
                try:
                    if not isinstance(row, dict) or not row:
                        raise ValueError("Row data is required.")
                    result = self.execute_action(
                        result,
                        {"action": "add", "data": row},
                    )
                except (ValueError, TypeError, OverflowError) as exc:
                    raise ValueError(
                        f"Cannot add row {number}: {exc}"
                    ) from exc
            return result
        if kind == "add":
            data = action.get("data")
            if (
                not isinstance(data, dict)
                or not data
            ):
                raise ValueError(
                    "Row data is required."
                )
            unknown = (
                set(data)
                - set(result.columns)
            )
            if unknown:
                raise ValueError(
                    f"Unknown columns: {sorted(unknown)}"
                )
            row = {}
            for column in result.columns:
                value = (
                    self.convert_value(
                        result[column],
                        data[column],
                    )
                    if column in data
                    else None
                )
                if value is None:
                    self._nullable_column(
                        result,
                        column,
                    )
                    dtype = result[column].dtype
                    value = (
                        pd.NA
                        if (
                            ptypes.is_integer_dtype(dtype)
                            or ptypes.is_bool_dtype(dtype)
                            or isinstance(
                                dtype,
                                pd.StringDtype,
                            )
                        )
                        else None
                    )
                row[column] = value
            addition = pd.DataFrame(
                [row],
                columns=result.columns,
            )
            # Preserve existing column dtypes.
            for column in result.columns:
                addition[column] = (
                    addition[column].astype(
                        result[column].dtype
                    )
                )
            return pd.concat(
                [result, addition],
                ignore_index=True,
            )
        # =================================
        # REMOVE DUPLICATE ROWS
        # =================================
        if kind == "remove_duplicates":
            return (
                result.drop_duplicates()
                .reset_index(drop=True)
            )
        raise ValueError(
            f"Unsupported action: {kind}"
        )
    # =====================================
    # DIRECT ROW HELPERS
    # =====================================
    def add_row(self, df, data):
        return self.execute_action(
            df,
            {
                "action": "add",
                "data": data,
            },
        )
    def add_rows(self, df, rows):
        """Convenience wrapper for multi-row additions."""
        return self.execute_action(
            df, {"action": "add_rows", "rows": rows}
        )
    def update_row(self, df, index, data):
        if index not in df.index:
            raise ValueError(
                "Row index not found."
            )
        result = df.copy(deep=True)
        for column, value in data.items():
            self.validate_column(
                result,
                column,
            )
            converted = self.convert_value(
                result[column],
                value,
            )
            if converted is None:
                self._nullable_column(
                    result,
                    column,
                )
                dtype = result[column].dtype
                converted = (
                    pd.NA
                    if (
                        ptypes.is_integer_dtype(dtype)
                        or ptypes.is_bool_dtype(dtype)
                        or isinstance(
                            dtype,
                            pd.StringDtype,
                        )
                    )
                    else None
                )
            result.loc[
                index,
                column,
            ] = converted
        return result
    def delete_row(self, df, index):
        if index not in df.index:
            raise ValueError(
                "Row index not found."
            )
        return (
            df.drop(index=index)
            .reset_index(drop=True)
        )
    # =====================================
    # EXPORT UPDATED EXCEL FILE
    # =====================================
    def export_excel(self, df):
        """
        Export the supplied DataFrame as XLSX.
        Original dataset column names and
        stored values are not translated.
        """
        if not isinstance(df, pd.DataFrame):
            raise ValueError(
                "Expected a pandas DataFrame."
            )
        output = BytesIO()
        df.to_excel(
            output,
            index=False,
            engine="openpyxl",
        )
        output.seek(0)
        return output
