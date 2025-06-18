import streamlit as st
from backend import nl_sql, user_memory

# --- Page Configuration ---
st.set_page_config(page_title="SQL Chatbot", page_icon="📊", layout="wide")

# --- Sidebar (Settings Panel) ---
with st.sidebar:
    st.header("⚙️ Settings")
    st.markdown("**Select Language**")
    st.selectbox("", ["Auto-Detect", "English", "Urdu", "Arabic"], index=0)
    st.button("🔄 Refresh Chat", on_click=lambda: st.session_state.pop("messages", None))

    st.markdown("""
        <hr/>
        <h5>📞 Contact Us</h5>
        <p><b>Phone:</b> +971 000 000 000</p>
        <p><b>Email:</b> <a href="mailto:sqlquery.ae">sqlquery.ae</a></p>
    """, unsafe_allow_html=True)

# --- Chat Header ---
st.markdown("""
    <h1 style='text-align: left; color: white;'>SQL Query Generator Assistant</h1>
    <p style='text-align: left;'>Hello! How can I help you today?</p>
""", unsafe_allow_html=True)

# --- Initialize Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize user memory only once
if "user_memory" not in st.session_state:
    st.session_state.user_memory = {"name": None}

# --- Display Chat History ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat Input Box ---
user_input = st.chat_input("Ask your question...")

# --- Handle User Input ---
if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.chat_message("assistant"):
        with st.spinner("Generating SQL query..."):
            sql_query = nl_sql(user_input, user_memory)  # ✅ Corrected
            st.markdown(f"""```sql\n{sql_query}\n```""")
            st.session_state.messages.append({"role": "assistant", "content": f"```sql\n{sql_query}\n```"})

