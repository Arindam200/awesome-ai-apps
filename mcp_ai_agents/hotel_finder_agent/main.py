from typing import Optional, Dict, Any
import json
import os

from agno.agent import Agent
from agno.models.nebius import Nebius
from agno.tools.mcp import MCPTools
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from textwrap import dedent
import asyncio
import base64
import streamlit as st
load_dotenv()

# Page config
st.set_page_config(
    page_title="Hotel Finder Agent",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS for better styling

# Header
st.markdown('<h1>🏨 Advanced Hotel Finder Agent</h1>', unsafe_allow_html=True)
st.markdown("**Discover the perfect hotels with AI-powered search and comprehensive filtering capabilities**")

# Setup sidebar for configuration
with st.sidebar:

    st.image("./assets/Nebius.png", width=150)
    api_key = st.text_input(
        "Nebius API Key",
        type="password",
        help="Enter your Nebius API key for AI model access"
    )

    if api_key:
        os.environ["NEBIUS_API_KEY"] = api_key

        st.divider()

    # Model Configuration
    st.markdown("#### 🤖 AI Model Settings")
    model_id = st.selectbox(
        "AI Model",
        ["deepseek-ai/DeepSeek-V3-0324","Qwen/Qwen3-30B-A3B", "Qwen/Qwen2.5-32B-Instruct", "meta-llama/Llama-3.3-70B-Instruct"],
        help="Select the AI model for processing queries"
    )

    temperature = st.slider(
        "Response Creativity",
        min_value=0.0,
        max_value=1.0,
        value=0.3,
        help="Lower values = more focused, Higher values = more creative"
    )


    st.divider()

    # Advanced Settings
    st.markdown("#### ⚙️ Advanced Settings")

    request_timeout = st.slider(
        "Request Timeout (seconds)",
        min_value=10,
        max_value=60,
        value=30,
        help="Maximum time to wait for hotel search results"
    )

    max_results = st.slider(
        "Max Results per Search",
        min_value=5,
        max_value=50,
        value=20,
        help="Maximum number of hotels to return per search"
    )


    st.markdown("---")

    st.markdown("Built with ❤️ by Arindam Majumder")



# Main search interface
# st.markdown("### 🔍 Hotel Search")

# Create tabs for different search modes
tab1, tab2 = st.tabs(["🏨 Quick Search", "🎯 Advanced Search"])

with tab1:
    st.markdown("#### Quick Hotel Search")

    col1, col2 = st.columns([2, 1])
    with col1:
        location = st.text_input(
            "📍 Location",
            value="Kolkata, India",
            placeholder="Enter city, state, or region",
            help="Enter the destination where you want to find hotels"
        )
    with col2:
        search_type = st.selectbox(
            "Search Type",
            ["Find Hotels", "Best Deals", "Luxury Hotels", "Budget Options", "Custom Query"]
        )

    # Generate query based on search type
    if search_type == "Find Hotels":
        base_query = f"Find available hotels in {location}"
    elif search_type == "Best Deals":
        base_query = f"Find hotels with best deals and discounts in {location}"
    elif search_type == "Luxury Hotels":
        base_query = f"Find luxury and premium hotels in {location}"
    elif search_type == "Budget Options":
        base_query = f"Find budget-friendly and affordable hotels in {location}"
    else:
        base_query = ""

    quick_query = st.text_area(
        "🗣️ Your Query",
        value=base_query,
        height=100,
        placeholder="Describe what kind of hotel you're looking for...",
        help="Use natural language to describe your hotel preferences"
    )

with tab2:
    st.markdown("#### Advanced Hotel Search with Filters")

    # Location and dates
    col1, col2, col3 = st.columns(3)
    with col1:
        adv_location = st.text_input(
            "📍 Destination",
            value="Kolkata, India",
            help="City, state, or specific area"
        )
    with col2:
        checkin_date = st.date_input(
            "📅 Check-in Date",
            value=datetime.now().date(),
            help="When do you want to check in?"
        )
    with col3:
        checkout_date = st.date_input(
            "📅 Check-out Date",
            value=(datetime.now() + timedelta(days=1)).date(),
            help="When do you want to check out?"
        )

    # Guests configuration
    st.markdown("#### 👥 Guest Information")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        adults = st.number_input("Adults", min_value=1, max_value=10, value=2)
    with col2:
        children = st.number_input("Children", min_value=0, max_value=8, value=0)
    with col3:
        infants = st.number_input("Infants", min_value=0, max_value=5, value=0)
    with col4:
        pets = st.number_input("Pets", min_value=0, max_value=5, value=0)



    # Additional preferences
    col1, col2 = st.columns(2)
    with col1:
        room_type = st.selectbox(
            "🏠 Room Type Preference",
            ["Any", "Single Room", "Double Room", "Suite", "Family Room", "Executive Room"]
        )
    with col2:
        star_rating = st.selectbox(
            "⭐ Minimum Star Rating",
            ["Any", "3+ Stars", "4+ Stars", "5 Stars Only"]
        )

    # Amenities
    st.markdown("#### 🏊 Preferred Amenities")
    amenities = st.multiselect(
        "Select amenities you want",
        ["WiFi", "Pool", "Gym", "Spa", "Restaurant", "Bar", "Parking", "Pet Friendly",
         "Business Center", "Airport Shuttle", "Room Service", "Concierge"]
    )

    # Build advanced query
    adv_query_parts = [f"Find hotels in {adv_location}"]

    if checkin_date and checkout_date:
        adv_query_parts.append(f"for dates {checkin_date} to {checkout_date}")

    guest_info = []
    if adults > 1:
        guest_info.append(f"{adults} adults")
    if children > 0:
        guest_info.append(f"{children} children")
    if infants > 0:
        guest_info.append(f"{infants} infants")
    if pets > 0:
        guest_info.append(f"{pets} pets")

    if guest_info:
        adv_query_parts.append(f"for {', '.join(guest_info)}")

    if room_type != "Any":
        adv_query_parts.append(f"preferably {room_type.lower()}")

    if star_rating != "Any":
        adv_query_parts.append(f"with {star_rating.lower()}")

    if amenities:
        adv_query_parts.append(f"with amenities: {', '.join(amenities)}")

    advanced_query = " ".join(adv_query_parts)

    st.text_area(
        "Generated Query",
        value=advanced_query,
        height=100,
        help="This query will be sent to the AI agent"
    )

# Dynamic response templates for different search modes
def get_response_template(search_mode: str, search_params: Dict[str, Any] = None) -> str:
    """
    Get the appropriate response template based on search mode

    Args:
        search_mode: The type of search (Quick Search, Advanced Search, Hotel Details)
        search_params: Search parameters for template customization

    Returns:
        Formatted instruction template for the specific search mode
    """

    if search_mode == "Quick Search":
        return f"""
        **QUICK SEARCH RESPONSE FORMAT:**

        ## 🏨 Quick Hotel Results

        ### 📍 Search Summary
        - **Location:** [location]
        - **Hotels Found:** [number]
        - **Search Type:** [search type from dropdown]

        ### 🏨 Hotel List

        For each hotel, use this format:

        **🏨 [Hotel Name]** ⭐ [rating]/5
        - 📍 **Location:** [address/area]
        - 💰 **Price:** $[price]/night
        - 🔗 **Book Now:** [booking link if available]
        - ✨ **Top Features:** [2-3 key amenities]
        - 📞 **Quick Info:** [phone or website]

        ---

        ### 🎯 Top Recommendations
        - **Best Deal:** [hotel name] - $[price]
        - **Highest Rated:** [hotel name] - [rating]⭐
        - **Prime Location:** [hotel name]

        ### 📞 Quick Actions
        - Click booking links for instant reservations
        - Call hotels directly for special rates
        - Use advanced search for more filtering options
        """

    elif search_mode == "Advanced Search":
        return f"""
        **ADVANCED SEARCH RESPONSE FORMAT:**

        ## 🎯 Advanced Hotel Search Results

        ### 📊 Detailed Search Summary
        - **Location:** [location]
        - **Check-in:** [checkin date] | **Check-out:** [checkout date]
        - **Guests:** [adults] adults, [children] children, [infants] infants, [pets] pets
        - **Room Type:** [room preference]
        - **Star Rating:** [star requirement]
        - **Amenities:** [selected amenities]
        - **Total Results:** [number] hotels found

        ### 🏨 Detailed Hotel Listings

        For each hotel, use this COMPREHENSIVE format:

        ---

        ## 🏨 [Hotel Name]

        | **Property Details** | **Information** |
        |---------------------|-----------------|
        | ⭐ **Rating** | [rating]/5 stars ([number] reviews) |
        | 📍 **Full Address** | [complete address with postal code] |
        | 💰 **Nightly Rate** | $[price] per night (taxes: $[tax amount]) |
        | 🏠 **Room Types** | [available room categories] |
        | 📏 **Distance** | [km from city center] • [km from airport] |
        | 🔗 **Booking Links** | [direct booking URL] |
        | 📞 **Contact** | [phone] • [website] |

        **✨ Complete Amenities List:**
        - 🏊 **Recreation:** [pool, gym, spa details]
        - 🍽️ **Dining:** [restaurant, bar, room service info]
        - 🚗 **Transport:** [parking, shuttle services]
        - 💼 **Business:** [meeting rooms, business center]
        - 🐕 **Pet Policy:** [pet-friendly details]
        - 🌐 **Connectivity:** [WiFi, internet details]
        - 🛎️ **Services:** [concierge, laundry, etc.]

        **📋 Booking Details:**
        - **Check-in:** [time] | **Check-out:** [time]
        - **Cancellation:** [detailed policy]
        - **Payment:** [accepted methods]
        - **Breakfast:** [inclusion/cost details]
        - **Parking:** [availability/cost]
        - **Extra Beds:** [policy and cost]

        **🎯 Match Analysis:**
        - **Budget Match:** [how it fits your budget]
        - **Amenity Match:** [matches X of Y requested amenities]
        - **Location Score:** [proximity ratings]
        - **Guest Rating:** [recent review highlights]

        **💡 Booking Recommendations:**
        - **Best for:** [specific use case]
        - **Special Offers:** [current promotions]
        - **Booking Tips:** [best rates, timing advice]

        [REPEAT FOR EACH HOTEL]

        ### 📈 Comparison Summary
        | Hotel | Rating | Price | Key Features | Booking Link |
        |-------|--------|-------|--------------|--------------|
        | [Hotel 1] | [rating]⭐ | $[price] | [top 2 features] | [link] |
        | [Hotel 2] | [rating]⭐ | $[price] | [top 2 features] | [link] |

        ### 🏆 Final Recommendations
        - **Best Overall Value:** [hotel name and detailed reason]
        - **Luxury Choice:** [hotel name and luxury features]
        - **Budget Winner:** [hotel name and savings details]
        - **Location Champion:** [hotel name and location benefits]
        - **Amenity Leader:** [hotel name and standout amenities]
        """
    return ""  # Default empty template

# Advanced hotel search function with enhanced error handling
async def run_hotel_agent(message: str, search_params: Dict[str, Any] = None) -> str:
    """
    Run the hotel finder agent with enhanced error handling and logging

    Args:
        message: The search query
        search_params: Additional search parameters

    Returns:
        Formatted response from the hotel agent
    """

    if not api_key:
        return "❌ **Error**: Nebius API key not provided. Please enter your API key in the sidebar."

    try:
        # Enhanced server parameters with additional configuration

        server_params = StdioServerParameters(
            command= "npx",
            args= [
                "-y",
                "@openbnb/mcp-server-airbnb",
                "--ignore-robots-txt"
            ],
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                mcp_tools = MCPTools(session=session)
                await mcp_tools.initialize()

                # Get the search mode from search_params
                search_mode = search_params.get('search_mode', 'Quick Search') if search_params else 'Quick Search'

                # Get the dynamic response template
                response_template = get_response_template(search_mode, search_params)

                # Enhanced agent configuration with dynamic template
                agent = Agent(
                    tools=[mcp_tools],
                    instructions=dedent(f"""\
                        You are an advanced Hotel Finder assistant powered by comprehensive Airbnb data through MCP tools.
                        Your goal is to help users find the best hotels based on their preferences and requirements.

                        **Core Capabilities:**
                        - Search for hotels/properties with advanced filtering (location, dates, guests, price range)
                        - Retrieve detailed property information including amenities, policies, and reviews
                        - Provide price comparisons and booking recommendations
                        - Analyze guest preferences and suggest personalized options

                        **CURRENT SEARCH MODE: {search_mode}**

                        **USER QUERY TO PROCESS:**
                        "{message}"

                        {response_template}

                        **TOOL USAGE INSTRUCTIONS:**
                        - Always use the airbnb_search tool first to find properties
                        - Pass the correct parameters (location is required, others optional)
                        - For hotel details queries, use airbnb_listing_details with the specific listing ID
                        - Use the available search parameters from the user's input
                        - Include direct Airbnb booking links in responses
                        - Use the search parameters provided above when making tool calls

                        **CRITICAL REQUIREMENTS:**
                        - Process the user query: "{message}" according to the {search_mode} format
                        - Follow the EXACT format specified above for {search_mode}
                        - Always use MCP tools to get real data before responding
                        - MUST include direct Airbnb booking links whenever available
                        - Show actual prices, ratings, and specific amenities from the API response
                        - Include full addresses and contact information when available
                        - If any information is not available from the API, clearly state "Not available"
                        - Use proper markdown formatting for tables and lists
                        - Make responses engaging with emojis and clear structure

                        **Error Handling:**
                        - If no properties are found, suggest alternative locations or date ranges
                        - If API limits are reached, explain the situation and suggest trying again later
                        - Always provide helpful context and next steps even with limited results
                        - If tool calls fail, explain what went wrong and provide alternatives
                    """),
                    markdown=True,
                    show_tool_calls=True,
                    model=Nebius(
                        id=search_params.get('model_id', 'deepseek-ai/DeepSeek-V3-0324') if search_params else model_id,
                        api_key=api_key,
                        temperature=search_params.get('temperature', 0.3) if search_params else temperature
                    )
                )

                response = await agent.arun(message)
                return response.content

    except asyncio.TimeoutError:
        return "⏰ **Timeout Error**: The hotel search took too long. Please try again with a more specific query or increase the timeout in settings."

    except Exception as e:
        error_msg = str(e)
        if "API rate limit" in error_msg.lower():
            return "🚦 **Rate Limit Error**: Too many requests. Please wait a moment before searching again."
        elif "authentication" in error_msg.lower():
            return "🔐 **Authentication Error**: Please check your API tokens and try again."
        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
            return "🌐 **Network Error**: Unable to connect to hotel services. Please check your internet connection."
        else:
            return f"❌ **Unexpected Error**: {error_msg}\n\nPlease try again or contact support if the issue persists."

# Helper function to validate search parameters
def validate_search_params(params: Dict[str, Any], search_mode: str = "Advanced Search") -> tuple[bool, str]:
    """Validate search parameters and return validation result based on search mode"""

    if search_mode == "Advanced Search":
        return validate_advanced_search_params(params)
    else:  # Quick Search
        return validate_quick_search_params(params)

def validate_advanced_search_params(params: Dict[str, Any]) -> tuple[bool, str]:
    """Validate parameters for advanced search"""
    location = params.get('location', '').strip()

    if not location:
        return False, "Location is required for hotel search"

    if len(location) < 2:
        return False, "Location must be at least 2 characters long"

    if params.get('checkin') and params.get('checkout'):
        try:
            checkin = datetime.strptime(params['checkin'], '%Y-%m-%d').date()
            checkout = datetime.strptime(params['checkout'], '%Y-%m-%d').date()
            if checkin >= checkout:
                return False, "Check-out date must be after check-in date"
            if checkin < date.today():
                return False, "Check-in date cannot be in the past"
        except ValueError:
            return False, "Invalid date format. Use YYYY-MM-DD"

    if params.get('adults', 1) < 1:
        return False, "At least 1 adult is required"

    return True, "Advanced search parameters are valid"

def validate_quick_search_params(params: Dict[str, Any]) -> tuple[bool, str]:
    """Validate parameters for quick search"""
    location = params.get('location', '').strip()

    if not location:
        return False, "Location is required for hotel search"

    if len(location) < 2:
        return False, "Location must be at least 2 characters long"

    return True, "Quick search parameters are valid"

# Initialize session state for active tab tracking
if 'active_search_tab' not in st.session_state:
    st.session_state.active_search_tab = "Quick Search"

# Determine which query to use based on the last non-empty query
query_to_execute = ""
search_parameters = {
    'timeout': request_timeout,
    'max_results': max_results,
    'model_id': model_id,
    'temperature': temperature
}

# Determine active search mode based on which query is being used
# Priority: Advanced > Quick (since advanced is most specific)
if advanced_query.strip():
    query_to_execute = advanced_query
    search_mode = "Advanced Search"
    search_parameters['search_mode'] = "Advanced Search"
    st.session_state.active_search_tab = "Advanced Search"
    # Add advanced search parameters with correct parameter names for Airbnb MCP
    search_parameters.update({
        'location': adv_location,
        'checkin': checkin_date.strftime('%Y-%m-%d') if checkin_date else None,
        'checkout': checkout_date.strftime('%Y-%m-%d') if checkout_date else None,
        'adults': adults,
        'children': children,
        'infants': infants,
        'pets': pets,
        'ignoreRobotsText': True
    })
elif quick_query.strip():
    query_to_execute = quick_query
    search_mode = "Quick Search"
    search_parameters['search_mode'] = "Quick Search"
    st.session_state.active_search_tab = "Quick Search"
    # Add basic location parameter for quick search - no dates included
    search_parameters.update({
        'location': location,
        'ignoreRobotsText': True
    })
else:
    st.warning("⚠️ Please enter a search query in one of the tabs above")
    query_to_execute = ""

# Show current active search mode
if query_to_execute:
    active_mode = st.session_state.get('active_search_tab', 'Unknown')

# Search execution buttons
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    execute_search = st.button(
        "🔍 Execute Hotel Search",
        type="primary",
        use_container_width=True,
        disabled=not query_to_execute.strip()
    )

with col2:
    if st.button("🔄 Clear Results", use_container_width=True):
        if 'search_results' in st.session_state:
            del st.session_state['search_results']
        st.rerun()

with col3:
    export_results = st.button(
        "📊 Export Results",
        use_container_width=True,
        disabled='search_results' not in st.session_state
    )

# Execute search
if execute_search:
    if not api_key:
        st.error("❌ Please enter your Nebius API key in the sidebar")
    elif not query_to_execute.strip():
        st.error("❌ Please enter a search query")
    else:
        # Validate search parameters based on search mode
        is_valid, validation_message = validate_search_params(search_parameters, search_mode)
        if not is_valid:
            st.error(f"❌ **Validation Error**: {validation_message}")
            st.stop()

        with st.spinner(f"🔍 Executing {search_mode.lower()}... This may take a moment."):
            try:
                # Show progress
                progress_bar = st.progress(0)
                status_text = st.empty()

                status_text.text("Initializing hotel search engine...")
                progress_bar.progress(20)

                status_text.text("Connecting to hotel data providers...")
                progress_bar.progress(40)

                status_text.text("Processing your query...")
                progress_bar.progress(60)

                # Execute the search
                result = asyncio.run(run_hotel_agent(query_to_execute, search_parameters))

                progress_bar.progress(80)
                status_text.text("Formatting results...")

                progress_bar.progress(100)
                status_text.text("Search completed!")

                # Store results in session state
                st.session_state['search_results'] = {
                    'query': query_to_execute,
                    'mode': search_mode,
                    'result': result,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'parameters': search_parameters
                }

                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()

            except Exception as e:
                st.error(f"❌ **Execution Error**: {str(e)}")
                st.info("💡 **Troubleshooting Tips:**")
                st.markdown("""
                - Check your internet connection
                - Verify your API tokens are correct
                - Try a simpler query
                - Reduce the timeout setting
                - Check if the hotel service is available
                """)

# Display search results
if 'search_results' in st.session_state:
    st.markdown("---")
    st.markdown("### 📋 Search Results")

    results_data = st.session_state['search_results']

    st.markdown(results_data['result'])

    # Export functionality
    if export_results:
        export_data = {
            'search_query': results_data['query'],
            'search_mode': results_data['mode'],
            'timestamp': results_data['timestamp'],
            'results': results_data['result'],
            'parameters': results_data['parameters']
        }

        st.download_button(
            label="📁 Download Results as JSON",
            data=json.dumps(export_data, indent=2),
            file_name=f"hotel_search_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )