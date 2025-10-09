import os

from calendar import c
from crewai import Agent, Task, Crew, Process
from crewai_tools import EXASearchTool
from dotenv import load_dotenv
from qdrant_tool import get_qdrant_tool
import agentops
import agentops
load_dotenv()

AGENTOPS_API_KEY = os.getenv("AGENTOPS_API_KEY")
agentops.init(
    api_key=AGENTOPS_API_KEY,
    default_tags=['crewai']
)

search_tool = EXASearchTool()
qdrant_tool = get_qdrant_tool()

db_search_agent = Agent(
    role="Senior Semantic Search Agent",
    goal="Find and analyze documents based on semantic search",
    backstory="""You are an expert research assistant who can find relevant
    information using semantic search in a Qdrant database.""",
    max_retry_limit=5,
    max_iter=5,
    tools=[qdrant_tool],
    verbose=True
)

search_agent = Agent(
    role="Senior Search Agent",
    goal="Search for relevant documents about the query using the Qdrant vector search tool",
    backstory="""You are an expert search assistant who can find relevant
    information about the query using the Qdrant vector search tool.""",
    tools=[search_tool],
    max_iter=2,
    verbose=True
)

answer_agent = Agent(
    role="Senior Answer Assistant",
    goal="Generate answers to questions based on the context provided",
    backstory="""You are an expert answer assistant who can generate
    answers to questions based on the context provided.""",
    verbose=True
)

db_search_task = Task(
    description="""Search for relevant documents about the {query}.
    Your final answer should include:
    - The relevant information found
    - The similarity scores of the results
    - The metadata of the relevant documents""",
    expected_output="A list of relevant documents with similarity scores and metadata.",
    agent=search_agent,
    tools=[qdrant_tool]
)

search_task = Task(
    description="""Search for relevant documents about the {query} using the Qdrant vector search tool.""",
    expected_output="Search results with relevant context and ranking.",
    agent=search_agent,
    tools=[search_tool]
)

answer_task = Task(
    description="""Given the context and metadata of relevant documents,
    generate a final answer based on the context.

    Example expected output (dynamically use context, results, and sources):

            ---
            # Answer to: "{query}"

            ## Summary

            Write the Summary of the findings here.

            ## Key Results

            - **Top relevant documents:**
            Write the list of documents with brief descriptions here.

            ## Details

            | Title | Similarity Score | Source | Date | Tags |
            |-------|------------------|--------|------|------|
            Fill this table with the relevant document information.

            ## Actionable Insights

            - Identify key trends and patterns in the search results.
            - Recommend specific actions based on the findings, such as further research or targeted outreach.
            - Highlight any gaps in the current knowledge base that need to be addressed.

            ## References
            List the Document Sources, or link to websites
            - [Document 1 Title](document1_link)
            - [Document 2 Title](document2_link)
            - [Document 3 Title](document3_link)

            ---

            Fill in each section using the context and results provided by previous agents. Use markdown elements for clarity and visual organization.
        """,
        expected_output="A comprehensive, visually clear, and well-formatted markdown text answer to the query, using proper markdown elements (not just a code block), including all relevant information, sources, and actionable insights.",
    agent=answer_agent
)

crew = Crew(
    agents=[db_search_agent, search_agent, answer_agent],
    tasks=[db_search_task, search_task, answer_task],
    process=Process.sequential,
    verbose=True
)