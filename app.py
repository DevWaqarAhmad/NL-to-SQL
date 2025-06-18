import streamlit as st
from backend import nl_sql

from langchain.memory import ConversationBufferMemory


st.set_page_config(page_title="SQL Chatbot", page_icon="📊", layout="wide")


with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("**Select Language**")
    st.selectbox("", ["Auto-Detect", "English", "Urdu", "Arabic"], index=0)

    def reset_chat():
        st.session_state.pop("messages", None)
        st.session_state.pop("user_memory", None)
        st.session_state.pop("memory", None)

    st.button("🔄 Refresh Chat", on_click=reset_chat)

    st.markdown("""
        <hr/>
        <h5>📞 Contact Us</h5>
        <p><b>Phone:</b> +971 000 000 000</p>
        <p><b>Email:</b> <a href="mailto:sqlquery.ae">sqlquery.ae</a></p>
    """, unsafe_allow_html=True)


st.markdown("""
    <h1 style='text-align: left; color: white;'>SQL Query Generator Assistant</h1>
    <p style='text-align: left;'>Hello! How can I help you today?</p>
""", unsafe_allow_html=True)


if "messages" not in st.session_state:
    st.session_state.messages = []

if "user_memory" not in st.session_state:
    st.session_state.user_memory = {"name": None}

if "memory" not in st.session_state:
    from langchain.memory import ConversationBufferMemory
    st.session_state.memory = ConversationBufferMemory(return_messages=True)


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])


user_input = st.chat_input("Ask your question...")

if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Generating SQL query..."):
            sql_query = nl_sql(user_input, st.session_state.user_memory, st.session_state.memory)

            
            if sql_query.lower().startswith("select") or " from " in sql_query.lower():
                reply = f"```sql\n{sql_query}\n```"
            else:
                reply = sql_query

            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
