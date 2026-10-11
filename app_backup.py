import hashlib
import streamlit as st
import pandas as pd

from database import (
    load_file,
    create_database,
    get_schema
)

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

defaults = {
    "messages": [],
    "database": None,
    "schema": None,
    "file_id": None,
}


for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value



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

    st.caption(
        "Powered by Gemini AI + SQLite"
    )



# ----------------------------------
# FILE CHECK
# ----------------------------------

if uploaded_file is None:

    if st.session_state.database:

        st.session_state.database.close()


    st.session_state.database = None
    st.session_state.schema = None
    st.session_state.file_id = None


    st.info(
        "📂 Upload a CSV or Excel file to start."
    )

    st.stop()



# ----------------------------------
# FILE HASH
# ----------------------------------

file_bytes = uploaded_file.getvalue()

file_id = hashlib.sha256(
    file_bytes
).hexdigest()



# ----------------------------------
# DATABASE CREATION
# ----------------------------------

if st.session_state.file_id != file_id:

    try:

        df = load_file(uploaded_file)


        connection = create_database(df)


        # Close previous connection
        if st.session_state.database:

            try:
                st.session_state.database.close()

            except Exception:
                pass


        st.session_state.database = connection


        st.session_state.schema = get_schema(
            connection
        )


        st.session_state.file_id = file_id


        st.session_state.messages = []


        st.success(
            "Database created successfully!"
        )


    except Exception as error:

        st.error(
            f"File processing failed: {error}"
        )

        st.stop()



# ----------------------------------
# SIDEBAR DATABASE INFO
# ----------------------------------

with st.sidebar:

    st.success(
        "Database ready!"
    )


    with st.expander(
        "🗄️ Database Schema"
    ):

        st.code(
            st.session_state.schema
        )



# ----------------------------------
# DATA PREVIEW
# ----------------------------------

with st.expander(
    "📊 Uploaded Data Preview",
    expanded=True
):

    try:

        preview = pd.read_sql_query(
            """
            SELECT *
            FROM uploaded_data
            LIMIT 5
            """,
            st.session_state.database
        )


        st.dataframe(
            preview,
            use_container_width=True
        )


    except Exception as error:

        st.error(
            f"Preview error: {error}"
        )



# ----------------------------------
# CHAT HISTORY
# ----------------------------------

for message in st.session_state.messages:


    with st.chat_message(
        message["role"]
    ):


        if message["role"] == "user":

            st.markdown(
                message["content"]
            )


        else:


            if message.get("sql"):

                st.markdown(
                    "**Generated SQL Query**"
                )

                st.code(
                    message["sql"],
                    language="sql"
                )



            if message.get("result") is not None:


                st.markdown(
                    "**Query Results**"
                )


                st.dataframe(
                    message["result"],
                    use_container_width=True
                )


                st.caption(
                    f"{len(message['result'])} rows returned"
                )



            if message.get("error"):

                st.error(
                    message["error"]
                )



# ----------------------------------
# CHAT INPUT
# ----------------------------------

question = st.chat_input(
    "Ask a question about your uploaded data..."
)



if question:


    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )


    with st.chat_message("user"):

        st.markdown(question)



    with st.chat_message("assistant"):


        with st.spinner(
            "Generating SQL and fetching data..."
        ):


            try:


                history = []


                sql = generate_sql(

                    question=question,

                    schema=st.session_state.schema,

                    history=history
                )



                result = execute_safe_query(

                    st.session_state.database,

                    sql
                )



                st.markdown(
                    "**Generated SQL Query**"
                )


                st.code(
                    sql,
                    language="sql"
                )



                st.markdown(
                    "**Query Results**"
                )


                st.dataframe(
                    result,
                    use_container_width=True
                )



                st.caption(
                    f"{len(result)} rows returned"
                )



                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "sql": sql,
                        "result": result,
                        "error": None
                    }
                )



            except Exception as error:


                st.error(
                    str(error)
                )


                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "sql": None,
                        "result": None,
                        "error": str(error)
                    }
                )