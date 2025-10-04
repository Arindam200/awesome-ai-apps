import os

from ai_services import translate_to_sql, explain_results
from database import parse_connection_string, execute_query
from dotenv import load_dotenv
import base64
import pandas as pd
import streamlit as st
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Talk to Database", page_icon="🗄️", layout="wide"
)

# Initialize session state
if "query_history" not in st.session_state:
    st.session_state.query_history = []

with open("./assets/langchain.png", "rb") as langchain_file:
    langchain_base64 = base64.b64encode(langchain_file.read()).decode()

with open("./assets/gibson.svg", "r", encoding="utf-8") as gibson_file:
    gibson_svg = gibson_file.read().replace('\n', '').replace('\r', '').replace('  ', '').replace('"', "'")

gibson_svg_inline = f'<span style="height:80px; width:200px; display:inline-block; vertical-align:middle; margin-left:8px;margin-top:20px;margin-right:8px;">{gibson_svg}</span>'

# Create title with embedded images (SVG and PNG in one line)
title_html = f"""
<div style='display:flex; align-items:center; width:100%; padding:24px 0;'>
  <h1 style='margin:0; padding:0; font-size:2.5rem; font-weight:bold; display:flex; align-items:center;'>
    <span style='font-size:3rem;'>🗄️ </span> Talk to Database with {gibson_svg_inline} &
    <img src='data:image/png;base64,{langchain_base64}' style='height:72px; margin-left:8px; margin-right:8px; vertical-align:middle;'/>
    Langchain
  </h1>
</div>
"""

def main():
    st.markdown(title_html, unsafe_allow_html=True)
    st.markdown("Ask questions about your ecommerce database in plain English!")

    # Sidebar for configuration
    with st.sidebar:
        st.image("./assets/nebius.png", width=150)


        # Nebius API Key input
        nebius_key = st.text_input(
            "Nebius API Key",
            type="password",
            value=os.getenv("NEBIUS_API_KEY", ""),
            help="Enter your Nebius API key",
        )

        if nebius_key:
            os.environ["NEBIUS_API_KEY"] = nebius_key

        st.markdown("---")
        st.markdown("### Database Connection")

        # Database connection string input
        connection_string = st.text_input(
            "Database Connection String",
            placeholder="mysql://username:password@host/database",
            help="Enter your MySQL connection string (format: mysql://username:password@host/database)",
            type="password",
        )

        if connection_string:
            # Parse connection string and store in session state
            db_config = parse_connection_string(connection_string)
            if db_config:
                st.session_state.db_config = db_config
                st.success("✅ Database connection configured!")
            else:
                st.error("❌ Invalid connection string format")
        else:
            st.warning("Please enter your database connection string")

        st.markdown("---")
        st.markdown("### Example Questions")
        st.markdown(
            """
        - "What are the product categories we have?"
        - "Show me all products with their prices"
        - "How many orders do we have?"
        - "What are the top 5 most expensive products?"
        """
        )


    # Question input
    question = st.text_area(
        "Enter your question in plain English:",
        height=100,
        placeholder="e.g., What are the product categories we have?",
    )

    if st.button("🚀 Generate SQL Query", type="primary"):
        if not question.strip():
            st.warning("Please enter a question!")
            return

        if not os.getenv("NEBIUS_API_KEY"):
            st.error("Please enter your Nebius API key in the sidebar!")
            return

        with st.spinner("Translating your question to SQL..."):
            sql_query = translate_to_sql(question)

            if sql_query and not sql_query.startswith("Error"):
                st.session_state.generated_sql = sql_query
                st.session_state.current_question = question
                st.success("SQL query generated successfully!")
            else:
                st.error(f"Failed to generate SQL query: {sql_query}")

    # Generated SQL section
    if "generated_sql" in st.session_state:
        st.markdown("---")
        st.header("📋 Generated SQL")
        st.code(st.session_state.generated_sql, language="sql")

        if st.button("▶️ Execute Query", type="secondary"):
            with st.spinner("Executing query..."):
                results, error = execute_query(st.session_state.generated_sql)

                if error:
                    st.error(error)
                else:
                    st.session_state.query_results = results
                    st.session_state.query_error = None
                    st.success("Query executed successfully!")

    # Results section
    if (
        "query_results" in st.session_state
        and st.session_state.query_results is not None
    ):
        st.markdown("---")
        st.header("📊 Query Results")

        # Display results as DataFrame
        df = pd.DataFrame(st.session_state.query_results)
        st.dataframe(df, use_container_width=True)

        # Show result count
        st.info(f"Found {len(df)} results")

        # Explain results in plain English
        if st.button("🤖 Explain Results"):
            with st.spinner("Generating explanation..."):
                explanation = explain_results(
                    st.session_state.query_results, st.session_state.current_question
                )
                st.markdown("### 📝 Explanation")
                st.write(explanation)

        # Add to history
        history_item = {
            "question": st.session_state.current_question,
            "sql": st.session_state.generated_sql,
            "results_count": len(df),
        }
        st.session_state.query_history.append(history_item)


if __name__ == "__main__":
    main()