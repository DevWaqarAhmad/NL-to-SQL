import json

from app.core.gemini import GeminiClient



class IntentRouter:


    def __init__(self):

        self.gemini = GeminiClient()



    def classify(
        self,
        question
    ):


        prompt = f"""

You are an AI data assistant.

Classify user request.

Only two categories exist:


1. query

User wants:

- search data
- analyze data
- count records
- find information
- generate reports



2. edit

User wants:

- delete records
- add data
- update values
- modify spreadsheet
- change data



Return ONLY JSON.


Examples:


User:
show cars from Pakistan

JSON:

{{
"type":"query"
}}



User:
delete all Pakistan records

JSON:

{{
"type":"edit"
}}



User:
change Ford brand to Toyota

JSON:

{{
"type":"edit"
}}



User:
how many cars are from China

JSON:

{{
"type":"query"
}}



User request:

{question}

"""


        try:


            text = self.gemini.generate(
                prompt
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



            result = json.loads(
                text.strip()
            )


            if "type" not in result:

                raise Exception(
                    "Invalid intent response"
                )


            return result



        except json.JSONDecodeError:


            raise Exception(
                "Intent Router returned invalid JSON:\n"
                + text
            )



        except Exception as error:


            raise Exception(
                f"Intent Router Error: {error}"
            )