
import hashlib
import streamlit as st
import pandas as pd

from database import load_file, create_database, get_schema
from backend import generate_sql
from sql_validator import execute_safe_query


# ----------------------------------
# PAGE CONFIGURATION
# ----------------------------------

st.set_page_config(
    page_title="NL-to-SQL AI Chatbot",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 NL-to-SQL AI Chatbot")
st.caption(
    "Upload Excel/CSV and ask questions about your data."
)


# ----------------------------------
# SESSION STATE
# ----------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "database" not in st.session_state:
    st.session_state.database = None

if "schema" not in st.session_state:
    st.session_state.schema = None

if "file_id" not in st.session_state:
    st.session_state.file_id = None


# ----------------------------------
# SIDEBAR
# ----------------------------------

with st.sidebar:
    st.header("⚙️ Settings")

    uploaded_file = st.file_uploader(
        "Upload CSV or Excel File",
        type=["csv", "xlsx"]
    )

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("Powered by Gemini AI + SQLite")


# ----------------------------------
# DATABASE SETUP
# ----------------------------------

if uploaded_file is None:
    if st.session_state.database is not None:
        st.session_state.database.close()

    st.session_state.database = None
    st.session_state.schema = None
    st.session_state.file_id = None
    st.session_state.messages = []

    st.info("📂 Upload a CSV or Excel file to start.")
    st.stop()


file_bytes = uploaded_file.getvalue()
file_id = hashlib.sha256(file_bytes).hexdigest()

if st.session_state.file_id != file_id:

    try:
        df = load_file(uploaded_file)

        connection = create_database(df)

        if st.session_state.database is not None:
            st.session_state.database.close()

        st.session_state.database = connection
        st.session_state.schema = get_schema(connection)
        st.session_state.file_id = file_id
        st.session_state.messages = []

    except Exception as error:
        st.error(f"File upload failed: {error}")
        st.stop()


with st.sidebar:
    st.success("Database ready!")

    with st.expander("🗄️ Database Schema"):
        st.code(st.session_state.schema)


with st.expander("📊 Uploaded Data Preview"):
    preview = pd.read_sql_query(
        "SELECT * FROM uploaded_data LIMIT 5",
        st.session_state.database
    )

    st.dataframe(
        preview,
        use_container_width=True
    )


# ----------------------------------
# DISPLAY CHAT HISTORY
# ----------------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        if message["role"] == "user":
            st.markdown(message["content"])

        else:
            if message.get("sql"):
                st.markdown("**Generated SQL Query**")
                st.code(message["sql"], language="sql")

            if message.get("result") is not None:
                st.markdown("**Query Results**")
                st.dataframe(
                    message["result"],
                    use_container_width=True
                )

                st.caption(
                    f"{len(message['result'])} rows returned"
                )

            if message.get("error"):
                st.error(message["error"])


# ----------------------------------
# CHAT INPUT + GEMINI AI
# ----------------------------------

question = st.chat_input(
    "Ask a question about your uploaded data..."
)

if question:

    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):

        with st.spinner("Generating and executing SQL..."):

            try:
                history = []

                # Collect previous successful questions.
                messages = st.session_state.messages[:-1]

                for i in range(len(messages) - 1):
                    current = messages[i]
                    next_message = messages[i + 1]

                    if (
                        current["role"] == "user"
                        and next_message["role"] == "assistant"
                        and next_message.get("sql")
                        and next_message.get("result") is not None
                    ):
                        history.append({
                            "question": current["content"],
                            "sql": next_message["sql"]
                        })

                sql = generate_sql(
                    question=question,
                    schema=st.session_state.schema,
                    history=history
                )

                result = execute_safe_query(
                    st.session_state.database,
                    sql
                )

                st.markdown("**Generated SQL Query**")
                st.code(sql, language="sql")

                st.markdown("**Query Results**")
                st.dataframe(
                    result,
                    use_container_width=True
                )

                st.caption(
                    f"{len(result)} rows returned"
                )

                st.session_state.messages.append({
                    "role": "assistant",
                    "sql": sql,
                    "result": result,
                    "error": None
                })

            except Exception as error:
                st.error(str(error))

                st.session_state.messages.append({
                    "role": "assistant",
                    "sql": None,
                    "result": None,
                    "error": str(error)
                })
