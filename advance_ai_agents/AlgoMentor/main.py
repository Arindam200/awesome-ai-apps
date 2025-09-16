import patch_sqlite 
import streamlit as st
from src.core.app import DSAAssistantApp
from config.settings import PAGE_TITLE, PAGE_LAYOUT, SIDEBAR_STATE

def main():
    """Main application entry point"""
    st.set_page_config(
        page_title=PAGE_TITLE,
        layout=PAGE_LAYOUT,
        initial_sidebar_state=SIDEBAR_STATE,
        page_icon="assets/logo.svg"
    )
    
    # Initialize and run the application
    app = DSAAssistantApp()
    app.run()

if __name__ == "__main__":
    main()