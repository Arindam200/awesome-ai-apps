import streamlit as st
import pymysql
from urllib.parse import urlparse


def parse_connection_string(connection_string):
    """Parse MySQL connection string and return database config"""
    try:
        # Parse the connection string
        parsed = urlparse(connection_string)

        # Extract components
        username = parsed.username
        password = parsed.password
        host = parsed.hostname
        port = parsed.port or 3306
        database = parsed.path.lstrip("/")

        return {
            "host": host,
            "user": username,
            "password": password,
            "database": database,
            "port": port,
            "ssl": {"ssl": {}},
        }
    except Exception as e:
        st.error(f"Error parsing connection string: {str(e)}")
        return None


def get_database_config():
    """Get database configuration from session state or default"""
    if "db_config" in st.session_state:
        return st.session_state.db_config
    return None


def get_database_connection():
    """Create and return a database connection"""
    try:
        db_config = get_database_config()
        connection = pymysql.connect(**db_config)
        return connection
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        return None


def execute_query(sql_query):
    """Execute SQL query and return results"""
    try:
        connection = get_database_connection()
        if not connection:
            return None, "Database connection failed"

        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql_query)
            results = cursor.fetchall()

        connection.close()
        return results, None

    except Exception as e:
        return None, f"Query execution error: {str(e)}"
