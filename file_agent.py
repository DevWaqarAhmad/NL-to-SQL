import os
import json

from dotenv import load_dotenv
from google import genai


load_dotenv()



class FileAgent:


    def __init__(self):


        api_key = os.getenv(
            "GEMINI_API_KEY"
        )


        if not api_key:

            raise ValueError(
                "Gemini API key missing"
            )


        self.client = genai.Client(
            api_key=api_key
        )



    def generate_action(
        self,
        question,
        columns
    ):


        prompt = f"""

You are an AI Excel editing assistant.

Your job is to understand user commands
and convert them into JSON actions.


Available columns:

{columns}



Allowed actions:


1. delete

Example:

User:
Delete all records where Country is Pakistan


Return:

{{
"action":"delete",
"column":"Country",
"value":"Pakistan"
}}



2. update

Example:

User:
Change all Ford brands to Toyota


Return:

{{
"action":"update",
"column":"Car_Brand",
"old_value":"Ford",
"new_value":"Toyota"
}}



3. add

Example:

User:
Add a new car Toyota Corolla Pakistan


Return:

{{
"action":"add",
"data":{{
"Car_Brand":"Toyota",
"Car_Model":"Corolla",
"Country":"Pakistan"
}}
}}



4. remove_duplicates

Return:

{{
"action":"remove_duplicates"
}}



Rules:

- Return ONLY JSON
- Never invent columns
- Use exact column names
- Do not explain



User command:

{question}

"""


        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )


        text = response.text.strip()



        text = text.replace(
            "```json",
            ""
        )


        text = text.replace(
            "```",
            ""
        )


        return json.loads(
            text.strip()
        )