from app.core.gemini import GeminiClient


class AIEngine:


    def __init__(self):

        self.gemini = GeminiClient()



    def generate_sql(
        self,
        question,
        schema
    ):


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
- Do not use markdown


User question:

{question}

"""


        sql = self.gemini.generate(
            prompt
        )


        sql = sql.strip()


        sql = sql.replace(
            "```sql",
            ""
        )


        sql = sql.replace(
            "```",
            ""
        )


        return sql.strip()



    def generate_answer(
        self,
        question,
        result
    ):


        prompt = f"""

You are an AI Data Analyst.

Answer the user question based only on the given data result.


User question:

{question}


Data result:

{result}


Rules:

- Reply only in the same language used by user.
- English question = English answer.
- Urdu question = Urdu answer.
- Roman Urdu question = Roman Urdu answer.
- Keep answer short and clear.
- Do not invent information.
- If no data exists, explain clearly.


"""


        answer = self.gemini.generate(
            prompt
        )


        return answer.strip()