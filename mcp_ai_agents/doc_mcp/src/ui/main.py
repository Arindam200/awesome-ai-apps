"""Main Gradio application for Doc-MCP."""

import logging

from dotenv import load_dotenv
import gradio as gr

from .tabs.ingestion import IngestionTab
from .tabs.management import ManagementTab
from .tabs.mcp import MCPTab
from .tabs.query import QueryTab
from .tabs.update import UpdateTab
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DocMCPApp:
    """Main application class for Doc-MCP Gradio interface."""

    def __init__(self):
        self.ingestion_tab = IngestionTab()
        self.query_tab = QueryTab()
        self.mcp_tab = MCPTab()
        self.management_tab = None
        self.update_tab = None

    def create_interface(self) -> gr.Blocks:
        """Create the main Gradio interface."""
        with gr.Blocks(
            title="Doc-MCP",
        ) as demo:
            # Header
            gr.Markdown("# 📚 Doc-MCP: Documentation RAG System")
            gr.Markdown(
                "Transform GitHub documentation repositories into accessible MCP (Model Context Protocol) servers for AI agents. "
                "Upload documentation, generate vector embeddings, and query with intelligent context retrieval."
            )

            self.management_tab = ManagementTab(demo)
            self.update_tab = UpdateTab(demo)

            # Tabs
            with gr.Tabs():
                self.ingestion_tab.create_tab()
                self.query_tab.create_tab()
                self.management_tab.create_tab()

                # Hidden API tab for programmatic access
                self.mcp_tab.create_tab()
                self.update_tab.create_tab()

        return demo

    def launch(self, **kwargs):
        """Launch the Gradio application."""
        demo = self.create_interface()
        return demo.launch(mcp_server=True)


def create_app() -> DocMCPApp:
    """Factory function to create application instance."""
    return DocMCPApp()


def main():
    """Main entry point for the application."""
    try:
        app = create_app()
        app.launch()
    except KeyboardInterrupt:
        logger.info("Application shutdown requested")
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        raise


if __name__ == "__main__":
    main()