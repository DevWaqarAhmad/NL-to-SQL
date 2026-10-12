
import json

from app.core.gemini import GeminiClient


class FileAgent:

    ALLOWED_ACTIONS = {
        "add",
        "update",
        "delete",
        "remove_duplicates"
    }

    ALLOWED_OPERATORS = {
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "contains",
        "is_null",
        "not_null"
    }

    def __init__(self):
        self.gemini = GeminiClient()

    def generate_action(self, question, columns):

        if not isinstance(question, str) or not question.strip():
            raise ValueError("Editing instruction is required.")

        columns = list(columns)

        if not columns:
            raise ValueError("Dataset has no columns.")

        prompt = f"""
You are DataPilot AI, a universal Excel/CSV editing agent.

Your job is to convert one user instruction into
exactly one structured JSON editing action.

The uploaded dataset may be about cars, economics,
finance, accounting, sales, education, or research.

ACTUAL DATASET COLUMNS:
{json.dumps(columns, ensure_ascii=False)}

Understand English, Urdu, and Roman Urdu.

IMPORTANT:
The actual column names are authoritative.
Never invent column names.
Never invent information the user did not provide.

ACTION FORMATS:

1. ADD ONE ROW

{{
  "action": "add",
  "data": {{
    "Country": "Pakistan",
    "Car_Brand": "Honda",
    "Car_Model": "City",
    "Car_Color": "White",
    "Year_of_Manufacture": 2020
  }}
}}

Only include columns explicitly specified or
unambiguously implied by the user.

Unspecified columns must be omitted from data.
The editing engine will handle missing values.

Example user instruction:
"Pakistan ki Honda City add kro white color 2020,
baqi details null rakh do"

If the available columns include the relevant car
fields, map the instruction to those exact fields.

Interpret:
- Honda as car brand
- City as car model
- White as car color
- 2020 as year of manufacture
- Pakistan as country

Do not put the complete phrase "Honda City" into
the brand field.

For other domains, interpret values based on
the actual available column names.

2. DELETE MATCHING ROWS

{{
  "action": "delete",
  "conditions": [
    {{
      "column": "Country",
      "operator": "eq",
      "value": "Pakistan"
    }}
  ]
}}

Example:
"Delete all Pakistan cars"

Delete only records matching the specified condition.

3. UPDATE MATCHING VALUES

{{
  "action": "update",
  "column": "Car_Color",
  "new_value": "White",
  "conditions": [
    {{
      "column": "Country",
      "operator": "eq",
      "value": "Pakistan"
    }},
    {{
      "column": "Car_Brand",
      "operator": "eq",
      "value": "Honda"
    }}
  ]
}}

Example:
"Change Honda cars in Pakistan to white"

4. REMOVE DUPLICATES

{{
  "action": "remove_duplicates"
}}

SUPPORTED CONDITION OPERATORS:

eq       equality
ne       inequality
gt       greater than
gte      greater than or equal
lt       less than
lte      less than or equal
in       membership in supplied list
contains case-insensitive substring
is_null  missing value
not_null non-missing value

FILTER RULES:

- Conditions are combined using AND.
- Use exact dataset column names.
- Do not invent conditions.
- Numeric values should be JSON numbers.
- Text values should be JSON strings.
- Null must be JSON null.
- For update and delete, use explicit conditions.
- Do not interpret unspecified filters as all rows.
- Do not turn analysis requests into edits.
- Do not invent entire rows.
- For add, only create a single row per action.

IMPORTANT LIMITATIONS:

- Only one editing action per request.
- No calculated column creation.
- No column renaming.
- No spreadsheet formula editing.
- No sorting or formatting operations.
- No arbitrary SQL or Python.
- Do not invent columns that do not exist.

If the request cannot be expressed safely using
the supported actions, return:

{{"action": "unsupported"}}

OUTPUT RULES:

- Return JSON only.
- No markdown.
- No code fences.
- No explanations.
- Use double-quoted JSON keys.
- Never include extra commentary.

USER INSTRUCTION:
{question}
"""

        try:
            response = self.gemini.generate(prompt)

            if not response:
                raise ValueError("Empty response from Gemini.")

            text = response.strip()

            if text.startswith("```"):
                lines = text.splitlines()

                if lines and lines[0].startswith("```"):
                    lines.pop(0)

                if lines and lines[-1].strip() == "```":
                    lines.pop()

                text = "\n".join(lines).strip()

            action = json.loads(text)

            self.validate_action(action, columns)

            return action

        except json.JSONDecodeError as error:
            raise ValueError(
                "Gemini returned invalid JSON."
            ) from error

    def validate_action(self, action, columns):

        if not isinstance(action, dict):
            raise ValueError(
                "AI action must be a JSON object."
            )

        action_type = action.get("action")

        if action_type not in self.ALLOWED_ACTIONS:
            raise ValueError(
                "Unsupported or ambiguous editing request. "
                "Please provide a more specific instruction."
            )

        if action_type == "add":
            self.validate_add(action, columns)

        elif action_type == "update":
            self.validate_update(action, columns)

        elif action_type == "delete":
            self.validate_delete(action, columns)

        elif action_type == "remove_duplicates":
            if set(action) != {"action"}:
                raise ValueError(
                    "Unexpected fields in remove_duplicates action."
                )

    def validate_add(self, action, columns):

        if set(action) != {"action", "data"}:
            raise ValueError(
                "Add action requires only action and data."
            )

        data = action.get("data")

        if not isinstance(data, dict) or not data:
            raise ValueError(
                "Add action requires valid row data."
            )

        for column, value in data.items():

            if column not in columns:
                raise ValueError(
                    f"Unknown column: {column}"
                )

            if isinstance(value, (dict, list)):
                raise ValueError(
                    f"Invalid value for column: {column}"
                )

    def validate_update(self, action, columns):

        if set(action) != {
            "action",
            "column",
            "new_value",
            "conditions"
        }:
            raise ValueError(
                "Update requires column, new_value "
                "and conditions."
            )

        column = action.get("column")

        if column not in columns:
            raise ValueError(
                f"Unknown update column: {column}"
            )

        if isinstance(action["new_value"], (dict, list)):
            raise ValueError(
                "Update value must be a scalar."
            )

        self.validate_conditions(
            action.get("conditions"),
            columns
        )

    def validate_delete(self, action, columns):

        if set(action) != {"action", "conditions"}:
            raise ValueError(
                "Delete requires filtering conditions."
            )

        self.validate_conditions(
            action.get("conditions"),
            columns
        )

    def validate_conditions(self, conditions, columns):

        if not isinstance(conditions, list) or not conditions:
            raise ValueError(
                "At least one filtering condition is required."
            )

        if len(conditions) > 10:
            raise ValueError(
                "Maximum 10 conditions are supported."
            )

        for condition in conditions:

            if not isinstance(condition, dict):
                raise ValueError(
                    "Invalid filtering condition."
                )

            column = condition.get("column")
            operator = condition.get("operator")

            if column not in columns:
                raise ValueError(
                    f"Unknown filter column: {column}"
                )

            if operator not in self.ALLOWED_OPERATORS:
                raise ValueError(
                    f"Unsupported filter operator: {operator}"
                )

            if operator in {"is_null", "not_null"}:
                if set(condition) != {"column", "operator"}:
                    raise ValueError(
                        "Null filter must not contain a value."
                    )
                continue

            if set(condition) != {
                "column",
                "operator",
                "value"
            }:
                raise ValueError(
                    "Filter requires column, operator and value."
                )

            value = condition["value"]

            if operator == "in":
                if (
                    not isinstance(value, list)
                    or not value
                    or any(
                        isinstance(item, (dict, list))
                        for item in value
                    )
                ):
                    raise ValueError(
                        "IN filter requires a list of scalar values."
                    )

            elif isinstance(value, (dict, list)):
                raise ValueError(
                    "Filter value must be a scalar."
                )

            if operator == "contains" and value is None:
                raise ValueError(
                    "Contains filter requires a text value."
                )

            if (
                operator in {"gt", "gte", "lt", "lte"}
                and value is None
            ):
                raise ValueError(
                    "Comparison filter requires a value."
                )
