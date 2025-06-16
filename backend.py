import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("API key not found")
#print(api_key)


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

# # Enhanced schema with sample data for better understanding
all_schemas = """
Available Tables and Example Data:

1. students(id INT, name TEXT, grade TEXT, percentage FLOAT)
   e.g., (1, 'Ali', 'A', 89.5)

2. staff(id INT, name TEXT, salary INT, department TEXT)
   e.g., (10, 'Asad', 100000, 'IT')

3. orders(order_id INT, customer_name TEXT, product_id INT, order_date DATE)
   e.g., (2001, 'Ahmed', 101, '2024-02-15')

4. products(product_id INT, name TEXT, price FLOAT, stock INT)
   e.g., (101, 'Laptop', 599.99, 20)

5. customers(id INT, name TEXT, city TEXT, phone TEXT)
   e.g., (1, 'Sara', 'Karachi', '03001234567')
"""

def nl_sql(nl_query):
    # Normalize input
    user_input = nl_query.lower().strip()

    
    casual_phrases = {
        "hi": "Hello! How can I assist you with an SQL query today?",
        "hello": "Hi there! Ask me anything related to databases or SQL.",
        "hey": "Hey! How can I help you?",
        "how are you?": "I'm just code, but I'm always ready to help you!",
        "how are you": "I'm just code, but I'm always ready to help you!",
        "what's up": "All good here! Ready to write some SQL for you.",
        "thank you": "You're welcome! Happy to help.",
        "thanks": "Glad to assist you!",
        "who are you": "I'm your SQL assistant. Ask me any database-related question.",
        "who are you?": "I'm your SQL assistant. Ask me any database-related question.",
        "what can you do": "I convert your natural language questions into SQL queries.",
        "bye": "Goodbye! Come back anytime if you need more help.",
        "see you": "See you soon! 😊",
        "good morning": "Good morning! Ready to dive into SQL?",
        "good afternoon": "Good afternoon! What can I generate for you?",
        "good evening": "Good evening! Need help with a query?",
        "how does this work": "Just type your question about the database, and I’ll generate the SQL for you!",
        "help": "Sure! Just ask a question like 'show all students' or 'get average salary'.",
        "are you a bot": "Yes, but a smart one! I generate SQL queries from your questions.",
        "hello there": "Hello! Ask me anything about your database.",
        "how’s it going": "All set to help you with SQL queries!",
        "greetings": "Greetings! Ready to work with some SQL?",
        "yo": "Yo! Need help with a database question?"
    }

    if user_input in casual_phrases:
        return casual_phrases[user_input]

    prompt = f"""
You are an AI assistant that converts user questions into valid SQL queries.

Here are the database schemas you can use:
{all_schemas}

Your task:
- Understand the user's intent.
- Generate a syntactically correct SQL query.
- Use JOINs, GROUP BY, WHERE, and aggregation functions if needed.
- Respond with **only** the SQL query (no explanation, no formatting).

Generate an SQL query for this question:
\"{nl_query}\"

Only return the SQL query. No explanation.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error: {e}"



# if __name__ == "__main__":
#     print("-" * 45)
#     print("Type your Question in natural language ")
#     print("-" * 45)

#     while True:
#         user_input = input("Ask your question: ")

#         if user_input.lower() in ["exit", "quit"]:
#             print("\nThanks for using the assistant. Goodbye! ")
#             break

#     sql_result = nl_sql(user_input)
#     print("Generated SQL Query:")
#     print(sql_result)
#     print("-" * 50)