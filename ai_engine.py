import os
from dotenv import load_dotenv
from google import genai


load_dotenv()


class AIEngine:

    def __init__(self):

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError(
                "Gemini API key missing in .env"
            )

        self.client = genai.Client(
            api_key=api_key
        )


    def generate_sql(self, question, schema):

        prompt = f"""
You are an expert AI Data Analyst.

Understand user questions in any language.

Convert natural language into DuckDB SQL.

Database table:
uploaded_data


Available columns:
{schema}


Rules:
- Return only SQL
- Only SELECT queries
- Never modify data
- Use only uploaded_data table


User question:
{question}
"""


        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )


        sql = response.text.strip()


        sql = sql.replace(
            "```sql",
            ""
        )

        sql = sql.replace(
            "```",
            ""
        )


        return sql.strip()