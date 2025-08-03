import streamlit as st
import os
import pandas as pd
from dotenv import load_dotenv

# Import functionality from separate modules
from database import parse_connection_string, execute_query
from ai_services import translate_to_sql, explain_results, generate_insert_sql_from_csv
import pandas as pd

# Load environment variables
load_dotenv()

# Page configuration
st.set_page_config(
    page_title="Natural Language Database Query", page_icon="🗄️", layout="wide"
)

# Initialize session state
if "query_history" not in st.session_state:
    st.session_state.query_history = []


def main():
    st.title("🗄️ Natural Language Database Query")
    st.markdown("Ask questions about your ecommerce database in plain English!")

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

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
            # Use default config
            from database import DEFAULT_DB_CONFIG

            st.session_state.db_config = DEFAULT_DB_CONFIG

        st.markdown("---")
        st.markdown("### Database Info")
        # st.info(f"Connected to: GibsonAI Ecommerce Database (MySQL)")
        # st.markdown(
        #     "**Tables:** category, product, product_category, user, order, order_item"
        # )
        st.markdown("**Note:** Uses MySQL syntax with backticks for identifiers")

        st.markdown("---")
        st.markdown("### 📁 File Upload")
        uploaded_file = st.file_uploader(
            "Upload CSV file for data insertion",
            type=["csv"],
            help="Upload a CSV file with columns: name, email, address",
        )

        if uploaded_file:
            try:
                # Read and preview the CSV
                df = pd.read_csv(uploaded_file)
                st.success(f"✅ File uploaded: {uploaded_file.name}")
                st.info(f"📊 File contains {len(df)} rows")

                # Show preview
                st.markdown("**File Preview:**")
                st.dataframe(df.head(), use_container_width=True)

                # Store the uploaded file data in session state
                st.session_state.uploaded_data = df.to_dict("records")
                st.session_state.uploaded_filename = uploaded_file.name

                # Show required columns info
                required_cols = ["name", "email", "address"]
                missing_cols = [col for col in required_cols if col not in df.columns]

                if missing_cols:
                    st.error(f"❌ Missing required columns: {', '.join(missing_cols)}")
                    st.info("Required columns: name, email, address")
                else:
                    st.success("✅ All required columns present")

                    # Add button to generate INSERT SQL
                    if st.button("🔧 Generate INSERT SQL", type="secondary"):
                        insert_sql = generate_insert_sql_from_csv(
                            st.session_state.uploaded_data
                        )
                        st.session_state.generated_insert_sql = insert_sql
                        st.success("✅ INSERT SQL generated!")
                        st.code(insert_sql, language="sql")

            except Exception as e:
                st.error(f"Error reading file: {str(e)}")

        st.markdown("---")
        st.markdown("### Example Questions")
        st.markdown(
            """
        - "What are the product categories we have?"
        - "Show me all products with their prices"
        - "How many orders do we have?"
        - "What are the top 5 most expensive products?"
        - "Generate SQL to insert the uploaded CSV data into the user table"
        """
        )

    # Main content area
    st.header("💬 Ask Your Question")

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
            # Get uploaded data if available
            uploaded_data = st.session_state.get("uploaded_data", None)

            sql_query = translate_to_sql(question, uploaded_data)

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

    # Generated INSERT SQL section (from uploaded file)
    if "generated_insert_sql" in st.session_state:
        st.markdown("---")
        st.header("📋 Generated INSERT SQL")
        st.code(st.session_state.generated_insert_sql, language="sql")

        if st.button("▶️ Execute INSERT Query", type="secondary"):
            with st.spinner("Executing INSERT query..."):
                results, error = execute_query(st.session_state.generated_insert_sql)

                if error:
                    st.error(error)
                else:
                    st.success("✅ Data inserted successfully!")
                    st.info(
                        f"Inserted {len(st.session_state.uploaded_data)} rows into the user table"
                    )

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

    # Query History
    if st.session_state.query_history:
        st.markdown("---")
        st.header("📚 Query History")

        for i, item in enumerate(reversed(st.session_state.query_history)):
            with st.expander(
                f"Query {len(st.session_state.query_history) - i}: {item['question'][:50]}..."
            ):
                st.write(f"**Question:** {item['question']}")
                st.code(item["sql"], language="sql")
                st.write(f"**Results:** {item['results_count']} rows")


if __name__ == "__main__":
    main()
