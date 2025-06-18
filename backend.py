import os
import string
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Google Gemini API key not found in environment.")

#print(api_key)
model = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=api_key,
    temperature=0.7
)
#____________---------------------

user_memory = {"name": None}

#__---------------------

all_schemas = """
Available Tables and Example Data:

1. students(id INT, name TEXT, grade TEXT, percentage FLOAT)
   e.g., (1, 'Ali', 'A', 89.5)

2. staff(id INT, name TEXT, salary INT, department TEXT, experience INT)
   e.g., (10, 'Asad', 100000, 'IT', 5)

3. orders(order_id INT, customer_name TEXT, product_id INT, order_date DATE)
   e.g., (2001, 'Ahmed', 101, '2024-02-15')

4. products(product_id INT, name TEXT, price FLOAT, stock INT)
   e.g., (101, 'Laptop', 599.99, 20)

5. customers(id INT, name TEXT, city TEXT, phone TEXT)
   e.g., (1, 'Sara', 'Karachi', '03001234567')
"""

#_---------------------

casual_phrases = {
    "hi": "Hello! How can I assist you with an SQL query today?",
    "hello": "Hi there! Ask me anything related to databases or SQL.",
    "my name is": "Nice to meet you!",
    "how are you": "I'm just code, but I'm always ready to help you!",
    "thanks": "You're welcome! Happy to help.",
    "thank you": "Glad to assist you!",
    "bye": "Goodbye! Come back anytime.",
    "see you": "See you soon! 😊",
    "what can you do": "I can convert your questions into SQL queries. Just ask!",
    "who are you": "I'm your SQL assistant bot. Ask me anything related to your database!",
    "what is your name": "You can call me your SQL helper!",
    "how does this work": "Just type your question about the database, and I’ll generate the SQL for you!",
    "are you a bot": "Yes, but a smart one! 😉",
    "what is sql": "SQL stands for Structured Query Language. It's used to manage and query data in databases.",
    "help": "Sure! Ask something like 'Show all students with grade A' or 'Get total sales'.",
    "tell me a joke": "Why do SQL developers never get lost? Because they always know the *JOIN* path!",
    "good morning": "Good morning! Ready to dive into SQL?",
    "good evening": "Good evening! Need help with a query?",
    "yo": "Yo! Need help with a database question?",
    "greetings": "Greetings! Ready to generate some SQL?"
}

#_---------------------

def nl_sql(nl_query, user_memory, memory):
    cleaned_query = nl_query.lower().strip()
    cleaned_query = cleaned_query.translate(str.maketrans('', '', string.punctuation))

    
    if cleaned_query in casual_phrases:
        response = casual_phrases[cleaned_query]
        memory.chat_memory.add_user_message(nl_query)
        memory.chat_memory.add_ai_message(response)
        return response

    
    if cleaned_query.startswith("my name is"):
        name = cleaned_query.replace("my name is", "").strip().title()
        user_memory["name"] = name
        response = f"Nice to meet you, {name}!"
        memory.chat_memory.add_user_message(nl_query)
        memory.chat_memory.add_ai_message(response)
        return response

    
    if any(q in cleaned_query for q in ["what is my name", "who am i"]):
        memory.chat_memory.add_user_message(nl_query)
        if user_memory["name"]:
            response = f"Your name is {user_memory['name']}."
        else:
            response = "I don't know your name yet. Please say 'My name is ...'"
        memory.chat_memory.add_ai_message(response)
        return response

    
    if any(k in cleaned_query for k in [
        "summarize", "summary", "what did we talk about", "show chat history",
        "show conversation", "chat summary", "show what we talked", "previous conversation",
        "review our chat", "give me a recap", "recap", "conversation summary",
        "what have we discussed", "tell me what we talked", "what we discussed",
        "what was the conversation", "show my chat", "summarize our chat",
        "can you summarize this", "brief me our chat", "summerize my chat"
    ]):
        messages = memory.chat_memory.messages
        if not messages:
            return "We haven’t had much of a chat yet!"

        condensed_history = "\n".join([
            f"User: {msg.content}" if isinstance(msg, HumanMessage) else f"Bot: {msg.content}"
            for msg in messages[-10:]
        ])

        summary_prompt = [
            SystemMessage(content="You're an assistant that summarizes conversations concisely."),
            HumanMessage(content=f"Summarize this conversation in 3-4 short bullet points:\n\n{condensed_history}")
        ]

        try:
            response = model.invoke(summary_prompt)
            summary = response.content.strip()
            memory.chat_memory.add_ai_message(summary)
            return f"🧾 Summary of our chat:\n\n{summary}"
        except Exception as e:
            return f"Sorry, couldn't generate summary. Error: {e}"

    
    memory.chat_memory.add_user_message(nl_query)

    
    system_instruction = SystemMessage(
        content=f"""You are an AI assistant that converts user questions into valid SQL queries.
Use the following database schema:
{all_schemas}
Only return valid SQL queries. No explanations."""
    )

    messages = [system_instruction] + memory.chat_memory.messages

    try:
        response = model.invoke(messages)
        sql_query = response.content.strip()
        memory.chat_memory.add_ai_message(sql_query)
        return sql_query
    except Exception as e:
        error_msg = f"Error: {e}"
        memory.chat_memory.add_ai_message(error_msg)
        return error_msg
