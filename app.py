import streamlit as st
from backend import nl_sql
from langchain.memory import ConversationBufferMemory
import pandas as pd

st.set_page_config(page_title="SQL Chatbot", page_icon="📊", layout="wide")

with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("**Upload Excel or CSV File**")
    uploaded_file = st.file_uploader("Upload Excel or CSV file", type=["xlsx", "csv"])

    if uploaded_file:
        file_name = uploaded_file.name.split(".")[0]  # 📌 e.g., book.xlsx → book

        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file, header=0)

        # Clean column names
        df.columns = df.columns.str.strip()
        df.columns = [col if col != "" else f"column_{i}" for i, col in enumerate(df.columns)]

        # Save to session state
        st.session_state["uploaded_df"] = df
        st.session_state["table_name"] = file_name
        st.session_state["dynamic_schema"] = ", ".join([f"[{col}] TEXT" for col in df.columns])

        # Show preview
        st.write("📊 Preview of your data:")
        st.dataframe(df.head())

    def reset_chat():
        st.session_state.pop("messages", None)
        st.session_state.pop("user_memory", None)
        st.session_state.pop("memory", None)
        st.session_state.pop("dynamic_schema", None)
        st.session_state.pop("uploaded_df", None)
        st.session_state.pop("table_name", None)

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
    st.session_state.memory = ConversationBufferMemory(return_messages=True)

# Chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input
user_input = st.chat_input("Ask your question...")

if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Generating SQL query..."):
            schema = st.session_state.get("dynamic_schema")
            table_name = st.session_state.get("table_name")

            # ✅ Fallback to default if no data file is uploaded
            if not schema or not table_name:
                schema = "id INT, name TEXT, grade TEXT, percentage FLOAT"
                table_name = "students"

            sql_query = nl_sql(
                user_input,
                st.session_state.user_memory,
                st.session_state.memory,
                schema=schema,
                table_name=table_name
            )

            if sql_query.lower().startswith("select") or " from " in sql_query.lower():
                reply = f"\n{sql_query}\n```"
            else:
                reply = sql_query

            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply})
