# 📊 SQL Query Generator Assistant

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-red)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


An AI-powered chatbot built using **Streamlit**, **Gemini API**, and **LangChain** that helps users convert natural language questions into valid **SQL queries**. Just upload your CSV or Excel file, describe your query in plain English, and get instant SQL output!

---

## 🚀 Features

- 🗣️ **Natural Language to SQL**: Just ask questions like:
  - *"Show all students with grade A"*
  - *"Get the total sales for June"*
- 📂 **Upload Your Own Data**: Supports `.csv` and `.xlsx` files
- 🤖 **AI-Powered Responses**: Uses Google’s Gemini model (via LangChain)
- 🧠 **Chat Memory**: Remembers your name and conversation context
- 📝 **Conversation Summarizer**: Generates a quick summary of your past chat
- 🔄 **Refresh Chat**: Easily reset the conversation with one click
- 📎 **Schema-Aware SQL Generation**: Automatically adapts SQL to your uploaded dataset

---

## 🛠️ Tech Stack

- **Frontend**: [Streamlit](https://streamlit.io/)
- **LLM Backend**: [Gemini API](https://ai.google.dev/)
- **Memory**: [LangChain's ConversationBufferMemory](https://docs.langchain.com/)
- **Environment Management**: Python `dotenv`
- **Data Handling**: `pandas`

---

## 📁 Project Structure

├── app.py # Streamlit UI code
├── backend.py # NLP to SQL logic with LangChain & Gemini
├── .env # Environment variables (API keys)
├── requirements.txt # Python dependencies
└── README.md # You're here!


---

## ✅ How to Run Locally

1. **Clone the Repo**
   ```bash
   git clone https://github.com/DevWaqarAhmad/sql-query-assistant.git
   cd sql-query-assistant

pip install -r requirements.txt

GEMINI_API_KEY=your_google_gemini_api_key

streamlit run app.py
🧪 Example Queries
Question	Generated SQL
Show all employees with salary > 5000	SELECT * FROM your_table WHERE salary > 5000;
Count the number of students	SELECT COUNT(*) FROM your_table;
Get average marks	SELECT AVG(marks) FROM your_table;

📬 Contact
📧 Email: devwaqarahmad@gmail.com

💡 Credits
Built with by Waqar Ahmad
Powered by Google Gemini API + LangChain

Let me know if you'd like GitHub repo badge, deployment badge (like Render, Vercel), or anything else added.


