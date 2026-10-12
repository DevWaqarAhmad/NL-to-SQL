
import os
from dotenv import load_dotenv
from google import genai

load_dotenv()


def generate_sql(question, schema, history=None):
    """Convert a natural-language question into SQLite SQL."""

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("GEMINI_API_KEY missing in .env file.")

    client = genai.Client(api_key=api_key)

    previous_questions = ""

    if history:
        previous_questions = "\n".join(
            f"User: {item['question']}\nSQL: {item['sql']}"
            for item in history[-5:]
        )

    prompt = f"""
You are an expert SQLite query generator.

Database table: uploaded_data

Database schema:
{schema}

Previous successful questions and SQL:
{previous_questions}

Current user question:
{question}

Rules:
1. Generate a valid SQLite SELECT query.
2. Use only the uploaded_data table.
3. Use only columns present in the schema.
4. Do not invent columns or tables.
5. For aggregate questions, use SQL aggregate functions.
6. Use previous questions only when context is needed.
7. Never generate INSERT, UPDATE, DELETE, DROP,
   ALTER, CREATE, PRAGMA, or ATTACH.
8. Return only SQL, without markdown or explanations.
9. If the question cannot be answered from the
   available schema, return CANNOT_ANSWER.
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={
            "temperature": 0
        }
    )

    if not response.text:
        raise ValueError("Gemini returned an empty response.")

    sql = response.text.strip()

    # Remove possible Markdown formatting.
    if sql.startswith("```"):
        lines = sql.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        sql = "\n".join(lines).strip()

    return sql
