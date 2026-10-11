
import json

from app.core.gemini import GeminiClient


class FileAgent:

    def __init__(self):
        self.gemini = GeminiClient()

    def generate_action(self, question, columns):
        if not question or not question.strip():
            raise ValueError("Editing instruction is required.")

        if not columns:
            raise ValueError("Dataset has no columns.")

        prompt = f"""
You are a universal Excel and CSV editing assistant.

Convert the user's natural-language editing request
into ONE valid JSON action.

The dataset may contain financial, economic, educational,
research, sales, or any other tabular information.

AVAILABLE COLUMNS:
{json.dumps(list(columns), ensure_ascii=False)}

SUPPORTED ACTIONS:

1. DELETE
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

2. UPDATE
{{
  "action": "update",
  "column": "GDP",
  "new_value": 450,
  "conditions": [
    {{
      "column": "Country",
      "operator": "eq",
      "value": "Pakistan"
    }},
    {{
      "column": "Year",
      "operator": "eq",
      "value": 2023
    }}
  ]
}}

3. ADD
{{
  "action": "add",
  "data": {{
    "Country": "Pakistan",
    "Year": 2024,
    "GDP": 450
  }}
}}

4. REMOVE DUPLICATES
{{
  "action": "remove_duplicates"
}}

ALLOWED OPERATORS:
eq, ne, gt, gte, lt, lte, in, contains,
is_null, not_null

EXAMPLE:
Delete rows where Salary is above 100000

{{
  "action": "delete",
  "conditions": [
    {{
      "column": "Salary",
      "operator": "gt",
      "value": 100000
    }}
  ]
}}

IMPORTANT RULES:
- Return exactly one JSON object.
- Return JSON only. No markdown or explanation.
- Use ONLY actual available column names.
- Never invent missing columns or data values.
- Preserve numeric values as JSON numbers.
- Use JSON strings for text and dates.
- Conditions are combined using AND.
- Never invent extra filtering conditions.
- For update/delete, conditions must be explicit.
- If user asks to edit all rows without a filter,
  do not guess a condition.
- Do not return executable SQL or Python code.
- If instruction is ambiguous or cannot be represented,
  return {{"action":"unsupported"}}.
- Understand English, Urdu and Roman Urdu.
- Only one action is supported per request.

USER INSTRUCTION:
{question}
"""

        try:
            text = self.gemini.generate(prompt)

            if not text:
                raise ValueError("Empty Gemini response.")

            text = text.strip()

            if text.startswith("```"):
                lines = text.splitlines()

                if lines and lines[0].startswith("```"):
                    lines.pop(0)

                if lines and lines[-1].strip() == "```":
                    lines.pop()

                text = "\n".join(lines).strip()

            action = json.loads(text)

            if not isinstance(action, dict):
                raise ValueError(
                    "Gemini must return a JSON object."
                )

            allowed = {
                "delete",
                "update",
                "add",
                "remove_duplicates"
            }

            action_type = action.get("action")

            if action_type not in allowed:
                raise ValueError(
                    "Unsupported or ambiguous editing request."
                )

            if action_type in {"update", "delete"}:
                conditions = action.get("conditions")

                # Retain support for the previous
                # single-column action format.
                legacy = (
                    "column" in action
                    and (
                        "value" in action
                        or "old_value" in action
                    )
                )

                if not conditions and not legacy:
                    raise ValueError(
                        "Update/delete requires explicit conditions."
                    )

                if conditions is not None:
                    if (
                        not isinstance(conditions, list)
                        or not conditions
                    ):
                        raise ValueError(
                            "Invalid filtering conditions."
                        )

                    for condition in conditions:
                        if not isinstance(condition, dict):
                            raise ValueError(
                                "Invalid condition format."
                            )

                        if condition.get("column") not in columns:
                            raise ValueError(
                                "AI referenced an unknown column."
                            )

            if action_type == "update":
                if action.get("column") not in columns:
                    raise ValueError(
                        "Update target column not found."
                    )

                if (
                    "new_value" not in action
                    and not (
                        "conditions" in action
                        and "value" in action
                    )
                ):
                    raise ValueError(
                        "Update requires a new value."
                    )

            if action_type == "add":
                data = action.get("data")

                if not isinstance(data, dict) or not data:
                    raise ValueError(
                        "Add requires row data."
                    )

                if any(col not in columns for col in data):
                    raise ValueError(
                        "AI referenced an unknown column."
                    )

            return action

        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid JSON returned by Gemini: {error}"
            ) from error
