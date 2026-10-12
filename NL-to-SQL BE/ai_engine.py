
import re

from app.core.gemini import GeminiClient


SUPPORTED_LANGUAGES = {
    "en": "English",
    "roman_ur": "Roman Urdu",
    "ur": "Urdu (اردو)",
}

DEFAULT_LANGUAGE = "en"

NO_QUERY_SENTINEL = "CANNOT_ANSWER"


class AIEngine:
    """
    DataPilot AI — multilingual dataset analysis engine.

    Converts dataset-related natural-language instructions
    into read-only DuckDB SQL and generates answers based
    strictly on the returned dataset results.
    """

    def __init__(self):
        self.gemini = GeminiClient()

    @staticmethod
    def _language_name(language):
        return SUPPORTED_LANGUAGES.get(
            language,
            SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE],
        )

    @staticmethod
    def _clean_response(response):
        if response is None:
            raise ValueError("AI returned an empty response.")

        text = str(response).strip()

        # Remove Markdown code fences, if present.
        text = re.sub(
            r"^\s*```(?:sql|duckdb|text)?\s*\n?",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(
            r"\n?\s*```\s*$",
            "",
            text,
        )

        return text.strip()

    def generate_sql(
        self,
        question,
        schema,
        language=DEFAULT_LANGUAGE,
    ):
        """
        Convert a dataset-related instruction into
        read-only DuckDB SQL.

        This method never executes SQL.
        Execution safety remains the responsibility
        of the backend SQL validator.
        """

        question = str(question).strip()

        if not question:
            raise ValueError("Please enter a dataset question.")

        if not schema:
            raise ValueError("Dataset schema is unavailable.")

        selected_language = self._language_name(language)

        prompt = f"""
You are DataPilot AI, an expert multilingual
data analyst and DuckDB SQL generator.

IMPORTANT:
This application is an instruction-based data tool,
NOT a general conversational chatbot.

TASK:
Understand the user's dataset-related question
and convert it into one valid read-only DuckDB
SQL query.

DATABASE INFORMATION:
Table name: uploaded_data

AVAILABLE SCHEMA:
{schema}

SELECTED USER LANGUAGE:
{selected_language}

LANGUAGE UNDERSTANDING RULES:
1. Understand instructions written in English,
   Roman Urdu, and Urdu script.
2. Understand common Roman Urdu spelling variations.
3. The selected language is a preference for
   user-facing responses. It does not change SQL.
4. Interpret the user's actual intent accurately.
5. Do not translate database column names.
6. Do not translate stored database values.
7. Map natural-language references to existing
   columns only when the mapping is unambiguous.
8. If the user refers to a column or condition
   that cannot be identified reliably, return
   CANNOT_ANSWER.

SQL GENERATION RULES:
1. Return only executable DuckDB SQL.
2. Generate exactly one SELECT statement.
3. Read-only WITH ... SELECT queries are allowed.
4. Use only the uploaded_data table.
5. Use only columns present in the schema.
6. Use DuckDB-compatible SQL syntax.
7. Quote column identifiers when necessary,
   including names containing spaces.
8. Properly escape SQL string literals.
9. Never generate INSERT, UPDATE, DELETE,
   DROP, ALTER, CREATE, TRUNCATE, COPY,
   MERGE, ATTACH, or other modifying commands.
10. Never access external files, URLs,
    databases, or extensions.
11. Do not invent records or database columns.
12. Do not return explanations, Markdown,
    comments, or JSON.
13. If the question cannot be answered using
    the provided dataset schema, return exactly:
    CANNOT_ANSWER

OUT-OF-SCOPE QUESTIONS:
If the user asks about general conversation,
greetings, your identity, your capabilities,
weather, politics, unrelated knowledge, or
anything not answerable from this dataset,
return exactly:
CANNOT_ANSWER

EXAMPLES:

User:
Show the first 10 records

SQL:
SELECT * FROM uploaded_data LIMIT 10;

User:
Pakistan ki sari cars dikhao

SQL:
Generate a valid SELECT query using the actual
schema column representing country, and filter
for the stored value representing Pakistan.
If no such column exists, return CANNOT_ANSWER.

User:
Dataset mein kitni rows hain?

SQL:
SELECT COUNT(*) AS total_rows FROM uploaded_data;

User:
Do you understand Roman Urdu?

Output:
CANNOT_ANSWER

USER QUESTION:
{question}

FINAL OUTPUT:
Return only the SQL statement or CANNOT_ANSWER.
"""

        response = self.gemini.generate(prompt)
        sql = self._clean_response(response)

        if not sql:
            raise ValueError(
                "AI could not generate a SQL query."
            )

        if sql.upper() == NO_QUERY_SENTINEL:
            raise ValueError(
                "This question is not supported by the "
                "current dataset. Please enter a "
                "dataset-related question or instruction."
            )

        return sql

    def generate_answer(
        self,
        question,
        result,
        language=DEFAULT_LANGUAGE,
    ):
        """
        Generate a concise explanation in the selected
        language using only actual query results.
        """

        question = str(question).strip()
        result = str(result).strip()

        selected_language = self._language_name(language)

        prompt = f"""
You are DataPilot AI, an expert multilingual
data analyst.

APPLICATION TYPE:
Instruction-based dataset analysis.
You are NOT a general conversational chatbot.

YOUR TASK:
Explain the provided query result accurately
and concisely.

SELECTED RESPONSE LANGUAGE:
{selected_language}

USER QUESTION:
{question}

ACTUAL QUERY RESULT:
{result}

RESPONSE RULES:
1. Respond in the selected response language.
2. If English is selected, write in English.
3. If Roman Urdu is selected, write Urdu using
   English/Latin letters only.
4. If Urdu is selected, write in Urdu script.
5. Follow the selected language even when the
   user's question was written in another language.
6. Use only information from ACTUAL QUERY RESULT.
7. Do not invent facts, values, or records.
8. Do not claim the dataset contains information
   that is absent from the result.
9. Keep numeric values accurate.
10. Preserve names, identifiers, column names,
    and stored dataset values.
11. Never claim that you edited the spreadsheet.
12. Keep the answer short, clear, and professional.
13. Avoid unnecessary greetings and conversation.
14. Do not include SQL or Markdown code fences.
15. If results are empty, explain that no matching
    records were returned.
16. Do not speculate about missing information.

LANGUAGE EXAMPLES:

English:
The dataset contains 150 records.

Roman Urdu:
Dataset mein total 150 records hain.

Urdu:
ڈیٹاسیٹ میں کل 150 ریکارڈز ہیں۔

FINAL ANSWER:
"""

        response = self.gemini.generate(prompt)

        answer = self._clean_response(response)

        if not answer:
            raise ValueError(
                "AI could not generate an answer."
            )

        return answer
