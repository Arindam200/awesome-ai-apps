![demo](./assets/demo.png)

# Talk to your Database 🤖

A powerful AI-powered database query tool that translates natural language questions into SQL queries using Nebius AI. This application allows users to interact with their MySQL databases using plain English, making database operations accessible to non-technical users.

## Features ✨

- 🗄️ **Natural Language Processing**: Ask database questions in plain English
- 🤖 **AI-Powered SQL Generation**: Uses Nebius AI to convert questions to SQL
- 📊 **Interactive Results**: View query results in clean, sortable tables
- 📝 **Business Insights**: Get AI-generated explanations of query results
- 📚 **Query History**: Track all your previous queries and results
- 🔍 **SQL Preview**: Review generated SQL before execution
- ⚙️ **Easy Configuration**: Simple setup with API keys and connection strings
- 🔒 **Secure Connections**: SSL-enabled database connections
- 🎯 **Example Questions**: Quick-start with pre-built examples

## Prerequisites 🛠️

- Python 3.10+
- [Nebius AI API key](https://dub.sh/AIStudio)
- [GibsonAI DB connection](https://www.gibsonai.com)
- MySQL database access

## Installation 📥

1. Clone the repository:

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd simple_ai_agents/talk_to_db
   ```

2. Install the required dependencies:

   ```bash
   uv sync
   ```

3. Create a `.env` file in the project root and add your API key:

   ```env
   NEBIUS_API_KEY=your_nebius_api_key
   ```

## Usage 🚀

1. Start the Streamlit application:

   ```bash
   uv run streamlit run app.py
   ```

2. Open your web browser and navigate to the provided local URL (typically http://localhost:8501)

3. Configure your settings in the sidebar:

   - **Nebius API Key**: Enter your Nebius AI API key
   - **Database Connection String**: Enter your MySQL connection string from [GibsonAI](https://www.gibsonai.com)

4. Ask questions in plain English:

   - "What are the product categories we have?"
   - "Show me all products with their prices"
   - "How many orders do we have?"
   - "What are the top 5 most expensive products?"
   - "Show me users and their order counts"

5. Review the generated SQL query

6. Execute the query to see results

7. Get AI-generated explanations of the results

## Database Connection 🔗

The application supports MySQL databases. Enter your connection string in the format:

```
mysql://username:password@host/database
```

## Supported Database Operations 📊

### Query Types

- **SELECT queries**: Data retrieval and analysis
- **Complex JOINs**: Multi-table queries
- **Aggregations**: COUNT, SUM, AVG operations
- **Filtering**: WHERE clauses and conditions
- **Sorting**: ORDER BY operations
- **Limiting**: LIMIT clauses for large datasets

### Example Queries

- "Show me all users who made orders"
- "What's the total revenue from completed orders?"
- "Which products are out of stock?"
- "Find the most popular product categories"
- "Show me recent orders with customer details"

## API Keys 🔑

- **Nebius AI API Key**: Get your API key from [https://tokenfactory.nebius.com/](https://dub.sh/AIStudio)

## Architecture 🏗️

### Modular Design

- **UI Layer** (`app.py`): Streamlit interface and user interactions
- **Database Layer** (`database.py`): Connection management and query execution
- **AI Layer** (`ai_services.py`): Natural language processing and SQL generation

### Key Components

- **Connection String Parser**: Safely parses MySQL connection strings
- **SQL Translator**: Converts natural language to SQL using Nebius AI
- **Result Explainer**: Provides business insights from query results
- **Query History**: Tracks and displays previous queries

## Example Workflow 🔄

1. **Ask a Question**: "What are the top 5 most expensive products?"
2. **AI Generates SQL**: `SELECT id, name, price FROM product ORDER BY price DESC LIMIT 5`
3. **Review SQL**: Check the generated query before execution
4. **Execute Query**: Run the query and see results
5. **Get Explanation**: AI explains the results in plain English
6. **Save to History**: Query is saved for future reference

## Contributing 🤝

Contributions are welcome! Please feel free to submit a Pull Request.

## License 📄

This project is licensed under the MIT License - see the LICENSE file for details.
