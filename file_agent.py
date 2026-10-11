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

Convert user command into JSON only.

Available columns:

{columns}


Allowed JSON actions:


DELETE:

{{
"action":"delete",
"column":"Column_Name",
"value":"Value"
}}


UPDATE:

{{
"action":"update",
"column":"Column_Name",
"old_value":"old",
"new_value":"new"
}}


ADD:

{{
"action":"add",
"data":{{
"Column":"Value"
}}
}}


REMOVE DUPLICATES:

{{
"action":"remove_duplicates"
}}



Rules:

- Return ONLY JSON.
- No explanation.
- Use exact column names.
- Never create fake columns.


User command:

{question}

"""


        try:

            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )


            if not response.text:

                raise Exception(
                    "Gemini returned empty response"
                )


            text = response.text.strip()



            # Remove markdown blocks

            text = text.replace(
                "```json",
                ""
            )

            text = text.replace(
                "```",
                ""
            )


            text = text.strip()



            action = json.loads(
                text
            )


            return action



        except json.JSONDecodeError:

            raise Exception(
                "Gemini returned invalid JSON:\n"
                + text
            )


        except Exception as error:

            raise Exception(
                f"File Agent Error: {error}"
            )