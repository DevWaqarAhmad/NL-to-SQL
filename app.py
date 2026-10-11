import streamlit as st

from data_engine import DataEngine
from ai_engine import AIEngine
from visualizer import Visualizer
from sql_validator import execute_safe_query
from excel_editor import ExcelEditor
from intent_router import IntentRouter
from file_agent import FileAgent



# --------------------------------
# PAGE CONFIG
# --------------------------------

st.set_page_config(
    page_title="AI Data Assistant",
    page_icon="🤖",
    layout="wide"
)


st.title("🤖 AI Data Assistant")

st.caption(
    "Analyze and edit your uploaded Excel/CSV files using natural language."
)



# --------------------------------
# SESSION STATE
# --------------------------------

if "data_engine" not in st.session_state:
    st.session_state.data_engine = DataEngine()


if "ai_engine" not in st.session_state:
    st.session_state.ai_engine = AIEngine()


if "visualizer" not in st.session_state:
    st.session_state.visualizer = Visualizer()


if "editor" not in st.session_state:
    st.session_state.editor = ExcelEditor()


if "intent_router" not in st.session_state:
    st.session_state.intent_router = IntentRouter()


if "file_agent" not in st.session_state:
    st.session_state.file_agent = FileAgent()


if "uploaded_df" not in st.session_state:
    st.session_state.uploaded_df = None


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

    st.header("⚙️ Upload Data")


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

                df = (
                    st.session_state
                    .data_engine
                    .load_file(
                        uploaded_file
                    )
                )


                st.session_state.uploaded_df = df.copy()


                st.session_state.schema = (
                    st.session_state
                    .data_engine
                    .get_schema()
                )


                st.session_state.current_file = uploaded_file.name


                st.session_state.messages = []


                st.success(
                    "File loaded successfully!"
                )


            except Exception as error:

                st.error(
                    str(error)
                )



    if st.session_state.schema:

        with st.expander(
            "🗄 Schema"
        ):

            st.code(
                st.session_state.schema
            )



# --------------------------------
# DATA PREVIEW
# --------------------------------

if st.session_state.uploaded_df is not None:


    with st.expander(
        "📊 Current Data Preview",
        expanded=False
    ):


        st.dataframe(
            st.session_state.uploaded_df.head(10),
            use_container_width=True
        )



    excel_file = (
        st.session_state
        .editor
        .export_excel(
            st.session_state.uploaded_df
        )
    )


    st.download_button(
        "⬇ Download Updated Excel",
        data=excel_file,
        file_name="updated_data.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


else:

    st.info(
        "Upload CSV or Excel file."
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
    "Ask or edit your data..."
)



if question:


    st.session_state.messages.append(
        {
            "role":"user",
            "content":question
        }
    )


    with st.chat_message("user"):

        st.write(question)



    with st.chat_message("assistant"):


        with st.spinner(
            "Updating file..."
        ):


            try:


                if st.session_state.uploaded_df is None:

                    raise Exception(
                        "Upload file first."
                    )



                # --------------------------------
                # INTENT DETECTION
                # --------------------------------

                intent = (
                    st.session_state
                    .intent_router
                    .classify(
                        question
                    )
                )



                # =================================
                # EDIT MODE
                # =================================

                if intent["type"] == "edit":


                    st.subheader(
                        "✏️ Editing File"
                    )


                    action = (
                        st.session_state
                        .file_agent
                        .generate_action(
                            question,
                            list(
                                st.session_state
                                .uploaded_df
                                .columns
                            )
                        )
                    )


                    st.code(
                        action,
                        language="json"
                    )


                    updated_df = (
                        st.session_state
                        .editor
                        .execute_action(
                            st.session_state.uploaded_df,
                            action
                        )
                    )


                    st.session_state.uploaded_df = updated_df


                    st.success(
                        "File updated successfully!"
                    )


                    st.subheader(
                        "📊 Updated Preview"
                    )


                    st.dataframe(
                        updated_df,
                        use_container_width=True
                    )


                    st.session_state.messages.append(
                        {
                            "role":"assistant",
                            "content":
                            "✏️ File updated successfully."
                        }
                    )


                    st.stop()



                # =================================
                # QUERY MODE
                # =================================


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



                result = execute_safe_query(
                    st.session_state
                    .data_engine
                    .connection,
                    sql
                )


                st.subheader(
                    "📊 Query Result"
                )


                st.dataframe(
                    result,
                    use_container_width=True
                )


                answer = (
                    st.session_state
                    .ai_engine
                    .generate_answer(
                        question,
                        result.to_string()
                    )
                )


                with st.expander(
                    "💬 AI Explanation"
                ):

                    st.write(answer)



                chart = (
                    st.session_state
                    .visualizer
                    .create_chart(
                        result
                    )
                )


                with st.expander(
                    "📈 Visualization"
                ):

                    if chart:

                        st.plotly_chart(
                            chart,
                            use_container_width=True
                        )


                st.session_state.messages.append(
                    {
                        "role":"assistant",
                        "content":
                        f"""
### 🧠 SQL Query

{sql}


### 💬 AI Explanation

{answer}
"""
                    }
                )


            except Exception as error:


                st.error(
                    str(error)
                )