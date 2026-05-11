![demo](./assets/adv-hotel-finder.gif)
# 🏨 Advanced Hotel Finder Agent

A comprehensive AI-powered hotel search and discovery application built with Streamlit and integrated with Model Context Protocol (MCP) servers. This application provides advanced filtering capabilities, detailed property information retrieval, and intelligent search recommendations.

## ✨ Features

### 🔍 Smart Search Capabilities

- **AI-Powered Queries**: Natural language hotel search with intelligent query processing
- **Multiple Search Modes**: Quick search, advanced filtering, and detailed hotel information
- **Location Intelligence**: Support for cities, states, regions, and specific areas
- **Date-Based Filtering**: Check-in and check-out date support with validation
- **Guest Configuration**: Flexible guest settings (adults, children, infants, pets)

### 🎯 Advanced Filtering

- **Price Range Control**: Set minimum and maximum price constraints per night
- **Room Type Preferences**: Filter by single, double, suite, family rooms, etc.
- **Star Rating Filters**: Minimum star rating requirements (3+, 4+, 5-star only)
- **Amenity Selection**: Multi-select amenities (WiFi, Pool, Gym, Spa, etc.)
- **Custom Preferences**: Tailored search based on specific requirements

### 📊 Comprehensive Results

- **Detailed Hotel Information**: Complete property details, amenities, and policies
- **Price Comparisons**: Clear pricing with per-night rates and total costs
- **Booking Integration**: Direct links to hotel booking platforms
- **Location Context**: Nearby attractions, transportation, and neighborhood info
- **Guest Reviews**: Ratings, reviews, and guest feedback integration

### 🛡️ Enhanced User Experience

- **Multi-Tab Interface**: Organized search modes for different use cases
- **Real-time Validation**: Input validation with helpful error messages
- **Progress Tracking**: Visual progress indicators during search execution
- **Result Management**: Save, export, and manage search results
- **Responsive Design**: Optimized for desktop and mobile viewing

## 🚀 Installation

### Prerequisites

- Python 3.11 or higher
- Nebius API key (for AI model access)

### Setup Instructions

1. **Clone the repository**:

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd mcp_ai_agents/hotel_finder_agent
   ```

2. **Install dependencies**:

   ```bash
   uv sync
   ```

3. **Set up environment variables** (optional):

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run the application**:
   ```bash
   streamlit run main.py
   ```
   then you'll get it running like that:

   ![demo](./assets/hotel-finder.gif)

## 🔧 Configuration

### API Keys

- **Nebius API Key**: Required for AI model access and query processing

### Advanced Settings

- **Request Timeout**: Configure maximum wait time for searches (10-60 seconds)
- **Max Results**: Set maximum number of hotels per search (5-50 results)
- **Robots.txt Compliance**: Option to bypass robots.txt restrictions
- **AI Model Selection**: Choose from available Nebius models
- **Response Creativity**: Adjust AI response temperature (0.0-1.0)

## 📖 Usage Guide

### Quick Search

1. Navigate to the "🏨 Quick Search" tab
2. Enter your destination location
3. Select a search type (Find Hotels, Best Deals, Luxury Hotels, etc.)
4. Modify the generated query if needed
5. Click "🔍 Execute Hotel Search"

### Advanced Search

1. Go to the "🎯 Advanced Search" tab
2. Fill in detailed search criteria:
   - Destination and dates
   - Guest information
   - Price range
   - Room preferences
   - Desired amenities
3. Review the generated query
4. Execute the search

### Hotel Details

1. Use the "📋 Listing Details" tab
2. Enter specific hotel ID or name
3. Provide location for better accuracy
4. Get comprehensive hotel information

## 🏗️ Architecture

### Core Components

- **Streamlit Frontend**: Interactive web interface with multi-tab layout
- **MCP Integration**: Model Context Protocol for hotel data access
- **AI Agent**: Nebius-powered natural language processing
- **Docker Integration**: Containerized MCP server execution
- **Async Processing**: Non-blocking search execution

### Data Flow

1. User inputs search criteria through Streamlit interface
2. Parameters are validated and formatted
3. MCP server is initialized with Docker
4. AI agent processes the query with hotel data access
5. Results are formatted and displayed with export options

### Security Features

- **API Key Management**: Secure handling of sensitive credentials
- **Input Validation**: Comprehensive parameter validation
- **Error Handling**: Graceful error management with user feedback
- **Rate Limiting**: Respectful API usage patterns
- **Timeout Protection**: Prevents hanging requests

## 📊 Export and Data Management

### Export Formats

- **JSON Export**: Complete search results with metadata
- **Structured Data**: Query parameters, timestamps, and results
- **Session Management**: Save and restore search sessions

### Data Preservation

- **Session State**: Results persist during application use
- **Search History**: Track previous searches and results
- **Parameter Memory**: Remember user preferences

## 🛠️ Development

### Project Structure

```
hotel_finder_agent/
├── main.py                 # Main Streamlit application
├── pyproject.toml         # Project configuration and dependencies
├── README.md              # This documentation
├── .env.example           # Environment variables template
├── assets/                # Static assets (logos, images)
└── tests/                 # Test files (optional)
```


## 🔍 Troubleshooting

### Common Issues

**Authentication Errors**:

- Verify API keys are entered correctly
- Check API key permissions and quotas
- Ensure hotel API token is valid

**Connection Issues**:

- Check internet connectivity
- Verify Docker is running and accessible
- Try increasing request timeout

**Search Errors**:

- Simplify complex queries
- Check date formats (YYYY-MM-DD)
- Validate location names and spelling

**Performance Issues**:

- Reduce maximum results count
- Increase timeout settings
- Use more specific search criteria

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

1. **Fork the repository** and create a feature branch
2. **Follow code style**: Use Black for formatting, isort for imports
3. **Add tests**: Include tests for new functionality
4. **Update documentation**: Keep README and docstrings current
5. **Submit a pull request** with clear description

### Code Style

- Use Python 3.11+ features and type hints
- Follow PEP 8 guidelines with Black formatting
- Use descriptive variable names and function documentation
- Include error handling and user feedback

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.

## 🙏 Acknowledgments

- **Streamlit Team**: For the excellent web app framework
- **MCP Protocol**: For standardized model-context integration
- **Nebius**: For AI model access and processing capabilities
- **Hotel Data Providers**: For comprehensive hotel information

## 📞 Support

- **Issues**: Report bugs on GitHub Issues
- **Documentation**: Additional docs in the repository
- **Community**: Join discussions about MCP and hotel search
