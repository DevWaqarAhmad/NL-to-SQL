import os
import string
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("Google Gemini API key not found in environment.")

#print(api_key)
#------------------------------------------------------------
model = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    google_api_key=api_key,
    temperature=0.7
)
#------------------------------------------------------------
user_memory = {"name": None}

#-------------------------------------------------------------
casual_phrases = {
    "hi": "Hello! How can I assist you with an SQL query today?",
    "hello": "Hi there! Ask me anything related to databases or SQL.",
    "hey": "Hey! Ready to turn your questions into SQL queries.",
    "thanks": "You're welcome! Happy to help.",
    "thank you": "You're very welcome!",
    "bye": "Goodbye! Come back anytime.",
    "goodbye": "See you again! Have a great day.",
    "what can you do": "I can convert your questions into SQL queries. Just ask!",
    "how does this work": "Just type your question about the database, and I’ll generate the SQL for you!",
    "help": "Sure! Ask something like 'Show all students with grade A' or 'Get total sales'.",
    "who made you": "I was built by Waqar Ahmad using Gemini API and LangChain!",
    "who created you": "Waqar Ahmad created me to help you write SQL queries easily.",
    "your name": "I'm your SQL Query Assistant!",
    "what is your name": "I'm the SQL Assistant chatbot — ready to help with queries.",
    "reset": "You can refresh the chat using the '🔄 Refresh Chat' button on the left sidebar.",
    "clear memory": "You can clear the conversation history by clicking the Refresh button."
}
#-------------------------------------------------------------

def nl_sql(nl_query, user_memory, memory, schema=None, table_name="your_table"):
    if not nl_query or not nl_query.strip():
        return "Please enter a valid question."

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
        "chat summary", "recap", "conversation summary"
    ]):
        chat_history = memory.chat_memory.messages if memory.chat_memory.messages else []
        
        if not chat_history:
            return "We haven’t had much of a chat yet!"

        condensed_history = "\n".join([
            f"User: {msg.content}" if isinstance(msg, HumanMessage) else f"Bot: {msg.content}"
            for msg in chat_history[-10:]
        ])

        summary_prompt = [
            SystemMessage(content="You're an assistant that summarizes conversations concisely."),
            HumanMessage(content=f"Summarize this conversation in 3-4 short bullet points:\n\n{condensed_history}")
        ]

        try:
            response = model.invoke(summary_prompt)
            summary = response.content.strip()

            # Format summary as pretty bullets
            if summary.startswith("- "):  # Bullet style from Gemini
                formatted_summary = "\n".join([f"• {line.lstrip('- ').strip()}" for line in summary.split("\n")])
            else:  # Plain text fallback
                formatted_summary = "\n".join([f"• {line.strip()}" for line in summary.split(".") if line.strip()])

            memory.chat_memory.add_ai_message(formatted_summary)
            return f"🧾 **Summary of our chat:**\n\n{formatted_summary}"
        except Exception as e:
            return f"Sorry, couldn't generate summary. Error: {e}"

    
    memory.chat_memory.add_user_message(nl_query)

    
    if not schema:
        schema = "id INT, name TEXT, grade TEXT, percentage FLOAT"

    
    system_instruction = SystemMessage(
        content=f"""You are an AI assistant that converts user questions into valid SQL queries.
Use the following table named `{table_name}` with the schema:
{schema}

Only return valid SQL queries using the table name `{table_name}`. No explanations."""
    )

    chat_history = memory.chat_memory.messages if memory.chat_memory.messages else []
    messages = [system_instruction] + chat_history

    try:
        response = model.invoke(messages)
        sql_query = response.content.strip()
        memory.chat_memory.add_ai_message(sql_query)
        return sql_query
    except Exception as e:
        error_msg = f"Error: {e}"
        memory.chat_memory.add_ai_message(error_msg)
        return error_msg
