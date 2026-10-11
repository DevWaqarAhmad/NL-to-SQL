import json

from app.core.gemini import GeminiClient



class FileAgent:


    def __init__(self):

        self.gemini = GeminiClient()



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



Allowed actions:



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


            text = self.gemini.generate(
                prompt
            )


            if not text:

                raise Exception(
                    "Empty Gemini response"
                )


            text = text.strip()



            text = text.replace(
                "```json",
                ""
            )

            text = text.replace(
                "```",
                ""
            )


            action = json.loads(
                text.strip()
            )


            return action



        except json.JSONDecodeError:


            raise Exception(
                "Invalid JSON returned by Gemini:\n"
                + text
            )



        except Exception as error:


            raise Exception(
                f"File Agent Error: {error}"
            )