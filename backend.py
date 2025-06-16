import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("API key not found")

genai.configure(api_key=api_key)

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config={
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "max_output_tokens": 2048
    }
)
#--------------------------------------------------------------------------------

all_schemas = """
Available Tables and their schemas:

1. students(id, name, grade, percentage)
2. staff(id, name, salary, department)
3. orders(order_id, customer_name, product_id, order_date)
4. products(product_id, name, price, stock)
5. customers(id, name, city, phone)
"""
#--------------------------------------------------------------------------------

def nl_sql(nl_query):
    prompt = f"""
You are an AI assistant that converts user questions into valid SQL queries.

Here are the database schemas you can use:
{all_schemas}

Generate an SQL query for this question:
\"{nl_query}\"

Only return the SQL query. No explanation.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f" Error: {e}"

#--------------------------------------------------------------------------------
# while True:
#     user_input = input("Ask your question ")
#     if user_input.lower() in ['exit ']:
#         print("HAve a Nice Day!")
#         break

#     sql_result = nl_sql(user_input)
#     print("Generated SQL Query:")
#     print(sql_result)
#     print("-" * 50)