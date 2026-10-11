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



    def generate_answer(self, question, result):

        prompt = f"""

You are an AI Data Analyst.

Answer the user question based only on the data result.

User question:

{question}


Data result:

{result}


Rules:

- Reply ONLY in the same language used by the user.
- If user asks in English, answer in English.
- If user asks in Urdu, answer in Urdu.
- If user asks in Roman Urdu, answer in Roman Urdu.
- Never change language automatically.
- Keep answer short and clear.
- Do not invent information.
- If result is empty, explain that no matching data was found.

"""


        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )


        return response.text.strip()