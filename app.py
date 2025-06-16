import streamlit as st
from backend import nl_sql

# ------------------ Page Setup ------------------ 
st.set_page_config(page_title="SQL Chatbot", page_icon="📊")
#st.write("WELCOME")
st.title("🧠 SQL Query Generator Assistant")
st.markdown("💬 Enter your natural language query, and I’ll convert it into a valid SQL statement.")

# ------------------ Refresh Button ------------------ 
if st.button("🔄 Refresh Chat"):
    st.session_state.messages = []
    st.experimental_rerun()

# ------------------ Initialize Chat History ------------------ 
if "messages" not in st.session_state:
    st.session_state.messages = []

# ------------------ Display Chat History ------------------ 
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ------------------ Casual Phrases & Smart Replies ------------------ 
casual_responses = {
    "hi": "👋 Hello! How can I help you with SQL today?",
    "hello": "Hi there! 👨‍💻 I'm here to generate SQL queries for you.",
    "how are you ?": "I'm just a bot, but I'm always ready to help! 😊",
    "what's up": "Not much, just waiting to turn your questions into SQL!",
    "who are you": "I'm your friendly SQL Assistant 🤖. Ask me anything SQL-related!",
    "thank you": "You're welcome! 🙌 Let me know if you have another query.",
    "thanks": "Glad to help! 👍",
    "bye": "Goodbye! 👋 Feel free to come back anytime.",
    "good morning": "Good morning! ☀️ Ready to generate some SQL?",
    "good night": "Good night! 🌙 Sleep tight and dream of databases!",
    "my name is " : "Nice to meet you! 😊 How can I assist you today?"
}

# ------------------ User Input ------------------ 
user_input = st.chat_input("✍️ Please enter your question:")

if user_input:
    cleaned_input = user_input.strip().lower()

    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    if cleaned_input in casual_responses:
        bot_reply = casual_responses[cleaned_input]
    else:
        with st.chat_message("assistant"):
            with st.spinner("🔍 Generating SQL query..."):
                sql_query = nl_sql(user_input)
                bot_reply = f"```sql\n{sql_query}\n```"

    
    with st.chat_message("assistant"):
        st.markdown(bot_reply)
    st.session_state.messages.append({"role": "assistant", "content": bot_reply})
