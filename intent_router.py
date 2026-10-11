import os
import json

from dotenv import load_dotenv
from google import genai


load_dotenv()


class IntentRouter:


    def __init__(self):

        api_key = os.getenv(
            "GEMINI_API_KEY"
        )

        self.client = genai.Client(
            api_key=api_key
        )



    def classify(self, question):


        prompt = f"""

You are an AI data assistant.

Classify the user request.

There are only two types:


1. query

User wants to:
- search data
- analyze data
- count records
- find information
- generate reports


2. edit

User wants to:
- delete records
- add data
- update values
- modify spreadsheet
- change columns


Return ONLY JSON.


Examples:


User:
show cars from Pakistan

Output:

{{
"type":"query"
}}



User:
delete all Pakistan records

Output:

{{
"type":"edit"
}}



User:
change Ford brand to Toyota

Output:

{{
"type":"edit"
}}



User:
how many cars are from China

Output:

{{
"type":"query"
}}



User request:

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