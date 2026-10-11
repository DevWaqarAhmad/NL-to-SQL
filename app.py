import streamlit as st

from data_engine import DataEngine
from ai_engine import AIEngine


# --------------------------------
# PAGE CONFIG
# --------------------------------

st.set_page_config(
    page_title="NL-to-SQL AI Analyst",
    page_icon="🤖",
    layout="wide"
)


st.title("🤖 NL-to-SQL AI Analyst")

st.caption(
    "Ask questions about your uploaded data in any language."
)


# --------------------------------
# SESSION STATE
# --------------------------------

if "data_engine" not in st.session_state:
    st.session_state.data_engine = DataEngine()


if "ai_engine" not in st.session_state:
    st.session_state.ai_engine = AIEngine()


if "schema" not in st.session_state:
    st.session_state.schema = None


if "messages" not in st.session_state:
    st.session_state.messages = []


if "current_file" not in st.session_state:
    st.session_state.current_file = None



# --------------------------------
# SIDEBAR
# --------------------------------

with st.sidebar:

    st.header("⚙️ Data Upload")


    uploaded_file = st.file_uploader(
        "Upload CSV / Excel",
        type=["csv", "xlsx"]
    )


    if st.button("🗑 Clear Chat"):

        st.session_state.messages = []

        st.rerun()



    if uploaded_file:


        if st.session_state.current_file != uploaded_file.name:


            try:

                st.session_state.data_engine.load_file(
                    uploaded_file
                )


                st.session_state.schema = (
                    st.session_state
                    .data_engine
                    .get_schema()
                )


                st.session_state.current_file = (
                    uploaded_file.name
                )


                st.session_state.messages = []


                st.success(
                    "Database ready!"
                )


            except Exception as error:

                st.error(
                    str(error)
                )



    if st.session_state.schema:


        with st.expander(
            "🗄 Database Schema"
        ):

            st.code(
                st.session_state.schema
            )



# --------------------------------
# DATA PREVIEW
# --------------------------------

if st.session_state.schema:


    with st.expander(
        "📊 Data Preview",
        expanded=True
    ):


        try:

            preview = (
                st.session_state
                .data_engine
                .preview(10)
            )


            st.dataframe(
                preview,
                use_container_width=True
            )


        except Exception as error:

            st.error(
                "Preview error: " + str(error)
            )


else:

    st.info(
        "Please upload CSV or Excel file."
    )



# --------------------------------
# CHAT HISTORY
# --------------------------------

for message in st.session_state.messages:


    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )



# --------------------------------
# USER QUESTION
# --------------------------------

question = st.chat_input(
    "Ask your question..."
)



if question:


    st.session_state.messages.append(
        {
            "role": "user",
            "content": question
        }
    )


    with st.chat_message("user"):

        st.write(question)



    with st.chat_message("assistant"):


        with st.spinner(
            "Analyzing data..."
        ):


            try:


                if not st.session_state.schema:

                    raise Exception(
                        "Upload data first."
                    )



                # -------------------------
                # Generate SQL
                # -------------------------

                sql = (
                    st.session_state
                    .ai_engine
                    .generate_sql(
                        question,
                        st.session_state.schema
                    )
                )



                st.subheader(
                    "🧠 Generated SQL"
                )


                st.code(
                    sql,
                    language="sql"
                )



                # -------------------------
                # Execute SQL
                # -------------------------

                result = (
                    st.session_state
                    .data_engine
                    .execute_query(sql)
                )



                st.subheader(
                    "📊 Result"
                )


                st.dataframe(
                    result,
                    use_container_width=True
                )



                # -------------------------
                # AI Explanation
                # -------------------------

                answer = (
                    st.session_state
                    .ai_engine
                    .generate_answer(
                        question,
                        result.to_string()
                    )
                )


                st.subheader(
                    "💬 AI Answer"
                )


                st.write(
                    answer
                )



                # -------------------------
                # Save Chat History
                # -------------------------

                history_text = (
                    "### 🧠 SQL Query\n\n"
                    + sql
                    + "\n\n"
                    + "### 💬 AI Answer\n\n"
                    + answer
                )


                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": history_text
                    }
                )



            except Exception as error:


                error_text = (
                    "❌ Error: "
                    + str(error)
                )


                st.error(
                    error_text
                )


                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": error_text
                    }
                )