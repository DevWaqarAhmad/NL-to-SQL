import os
import json
from dotenv import load_dotenv
from google import genai


load_dotenv()


class AIEditor:


    def __init__(self):

        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        self.client = genai.Client(
            api_key=api_key
        )


    def understand_edit(self, question, columns):


        prompt = f"""

You are a data editing assistant.

Understand user's command.

Available columns:

{columns}


Return ONLY JSON.


Actions:

add
update
delete


Examples:

User:
delete Pakistan country data


Return:

{{
"action":"delete",
"column":"Country",
"value":"Pakistan"
}}


User:
add new car Toyota Corolla Pakistan 2026


Return:

{{
"action":"add",
"data":{{
"Car_Brand":"Toyota",
"Car_Model":"Corolla",
"Country":"Pakistan",
"Year_of_Manufacture":2026
}}
}}


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


        return json.loads(text.strip())