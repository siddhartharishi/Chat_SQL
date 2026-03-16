import streamlit as st
import pathlib
import requests
from sqlalchemy import create_engine

from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.base import create_sql_agent

import mysql.connector


st.set_page_config(page_title="LangChain SQL Chat", page_icon="🦜")
st.title("🦜 Chat with SQL Database")

CLOUDDB = "CLOUD_DB"
MYSQL = "LOCAL_DB"

options = [
    "Connect to Cloud Storage",
    "Connect to Local Database"
]

selected = st.sidebar.radio("Choose Database", options)

# -----------------------------
# Database selection
# -----------------------------

if options.index(selected) == 1:
    db_type = MYSQL
    mysql_host = st.sidebar.text_input("MySQL Host")
    mysql_user = st.sidebar.text_input("MySQL User")
    mysql_password = st.sidebar.text_input("MySQL Password", type="password")
    mysql_db = st.sidebar.text_input("Database Name")

else:
    db_type = CLOUDDB
    mysql_url = st.sidebar.text_input("DB Cloud Storage URL")


# -----------------------------
# OPENAI API KEY
# -----------------------------

api_key = st.sidebar.text_input("OPENAI API Key", type="password")

if not api_key:
    st.info("Please enter your OPENAI API key")
    st.stop()

# -----------------------------
# LLM
# -----------------------------

llm = ChatOpenAI(
    api_key=api_key,
    model="gpt-4o",
    temperature=0
)

# -----------------------------
# Database configuration
# -----------------------------

@st.cache_resource(ttl=7200)
def configure_db(db_type, mysql_host=None, mysql_user=None, mysql_password=None, mysql_db=None, mysql_url=None):

    if db_type == CLOUDDB:

        if not mysql_url:
            st.error("Please provide the cloud DB URL")
            st.stop()

        local_path = pathlib.Path("clouddb_url.db")

        if not local_path.exists():
            response = requests.get(mysql_url)

            if response.status_code == 200:
                local_path.write_bytes(response.content)
            else:
                st.error("Failed to download database file")
                st.stop()

        return SQLDatabase.from_uri(f"sqlite:///{local_path}")

    elif db_type == MYSQL:

        if not (mysql_host and mysql_user and mysql_password and mysql_db):
            st.error("Please provide all MySQL details")
            st.stop()

        connection_string = (
            f"mysql+mysqlconnector://{mysql_user}:{mysql_password}@{mysql_host}/{mysql_db}"
        )

        engine = create_engine(connection_string)

        return SQLDatabase(engine)


# -----------------------------
# Initialize Database
# -----------------------------

if db_type == MYSQL:

    db = configure_db(
        db_type,
        mysql_host,
        mysql_user,
        mysql_password,
        mysql_db
    )

else:

    db = configure_db(
        db_type,
        mysql_url=mysql_url
    )

# -----------------------------
# Create SQL Agent
# -----------------------------

toolkit = SQLDatabaseToolkit(
    db=db,
    llm=llm
)
prompt = """
You are an agent designed to interact with a SQL database.

You MUST follow this format exactly:

Thought: reasoning about what to do
Action: the tool to use, one of
[sql_db_list_tables, sql_db_schema, sql_db_query, sql_db_query_checker]
Action Input: the input to the tool
Observation: the result returned by the tool

Repeat the Thought/Action/Observation steps as needed.

When you know the final answer:

Thought: I now know the final answer
Final Answer: the answer to the user.

Rules:
- Never answer conversationally without using a tool.
- Always start by listing tables using sql_db_list_tables.
- Never wrap SQL queries in markdown.
- Return raw SQL when executing queries.
- Do not modify the database (no INSERT, UPDATE, DELETE, DROP).
"""

agent = create_sql_agent(
    llm=llm,
    toolkit=toolkit,
    prefix=prompt,
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=10
)

# -----------------------------
# Chat History
# -----------------------------

if "messages" not in st.session_state or st.sidebar.button("Clear Chat History"):
    st.session_state["messages"] = [
        {"role": "assistant", "content": "Ask me anything about your database."}
    ]

for message in st.session_state.messages:
    st.chat_message(message["role"]).write(message["content"])

# -----------------------------
# Chat Input
# -----------------------------

user_prompt = st.chat_input("Ask a question about your database")

if user_prompt:

    st.session_state.messages.append(
        {"role": "user", "content": user_prompt}
    )

    st.chat_message("user").write(user_prompt)

    with st.chat_message("assistant"):

        try:
            result = agent.invoke({"input": user_prompt})
            answer = result["output"]

        except Exception as e:
            answer = f"⚠️ Error: {str(e)}"

        st.session_state.messages.append(
            {"role": "assistant", "content": answer}
        )

        st.write(answer)
