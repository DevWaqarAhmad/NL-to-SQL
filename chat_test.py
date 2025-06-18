from langchain.memory import ConversationBufferMemory
from backend import nl_sql, user_memory

memory = ConversationBufferMemory(return_messages=True)

print("\n🤖 SQL Chatbot (Terminal Test Mode)")
print("Type 'exit' to quit or 'summary' to get a summary.\n")

while True:
    user_input = input("🧑 You: ")
    if user_input.lower() in ["exit", "quit"]:
        print("🤖 Bot: Goodbye!")
        break

    response = nl_sql(user_input, user_memory, memory)
    print(f"🤖 Bot:\n{response}\n")
