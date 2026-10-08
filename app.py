
import streamlit as st
import pandas as pd

from database import (
    load_file,
    create_database,
    get_schema,
    execute_query
)

# -----------------------------
# PAGE CONFIGURATION
# -----------------------------

st.set_page_config(
    page_title="NL-to-SQL AI Chatbot",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 NL-to-SQL AI Chatbot")
st.caption("Ask questions about your data using natural language.")

# -----------------------------
# SESSION STATE
# -----------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

if "database" not in st.session_state:
    st.session_state.database = None

if "schema" not in st.session_state:
    st.session_state.schema = None

if "file_id" not in st.session_state:
    st.session_state.file_id = None

# -----------------------------
# SIDEBAR
# -----------------------------

with st.sidebar:
    st.header("⚙️ Settings")

    uploaded_file = st.file_uploader(
        "Upload Excel or CSV",
        type=["csv", "xlsx"]
    )

    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()

# -----------------------------
# LOAD FILE & DATABASE
# -----------------------------

if uploaded_file is not None:

    file_id = (
        uploaded_file.name,
        uploaded_file.size,
        uploaded_file.getvalue()
    )

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

            st.success("✅ File uploaded and database created!")

        except Exception as error:
            st.error(f"File processing failed: {error}")
            st.stop()

    with st.expander("📊 Uploaded Data Preview", expanded=True):
        preview = pd.read_sql_query(
            "SELECT * FROM uploaded_data LIMIT 5",
            st.session_state.database
        )
        st.dataframe(preview, use_container_width=True)

    with st.expander("🗄️ Database Schema"):
        st.code(st.session_state.schema)

else:
    if st.session_state.database is not None:
        st.session_state.database.close()

    st.session_state.database = None
    st.session_state.schema = None
    st.session_state.file_id = None
    st.session_state.messages = []

    st.info("📂 Upload a CSV or Excel file to get started.")
    st.stop()

# -----------------------------
# CHAT HISTORY
# -----------------------------

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        if message["role"] == "user":
            st.markdown(message["content"])

        else:
            st.code(message["sql"], language="sql")
            st.dataframe(message["result"], use_container_width=True)

# -----------------------------
# TEMPORARY SQL TEST
# -----------------------------

st.subheader("🧪 SQL Execution Test")

sql_input = st.text_area(
    "Enter a SQL SELECT query:",
    value="SELECT * FROM uploaded_data LIMIT 10"
)

if st.button("▶️ Execute SQL"):

    sql = sql_input.strip()

    # Temporary testing guard; a full SQL validator
    # will be implemented in the next step.
    if not sql.lower().startswith("select"):
        st.error("Only SELECT queries are allowed in this test.")
        st.stop()

    try:
        # Set SQLite connection to query-only mode.
        st.session_state.database.execute("PRAGMA query_only = ON")

        result = execute_query(
            st.session_state.database,
            sql
        )

        st.session_state.messages.append({
            "role": "user",
            "content": f"Execute SQL: {sql}"
        })

        st.session_state.messages.append({
            "role": "assistant",
            "sql": sql,
            "result": result
        })

        st.rerun()

    except Exception as error:
        st.error(f"SQL execution failed: {error}")
