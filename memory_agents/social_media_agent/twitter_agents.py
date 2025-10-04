"""
Twitter Post Agent with Composio Integration

Agent functions for:
1. Style Analysis Agent: Scrapes user's tweets and analyzes tweeting style using Nebius
2. Tweet Generation Agent: Generates tweets using stored style and posts via Composio

Requirements:
- pip install streamlit composio openai python-dotenv langchain_scrapegraph langchain_nebius memori
- Set environment variables from env_template.txt
"""

from typing import Dict, Any, List
import json
import os

from dotenv import load_dotenv
load_dotenv()

# Import required libraries
from composio import Composio
from openai import OpenAI
from langchain_scrapegraph.tools import SmartScraperTool
from langchain_nebius import ChatNebius
from memori import Memori, create_memory_tool
from create_tweet import create_tweet

# Check for required environment variables
required_vars = [
    "COMPOSIO_API_KEY",
    "OPENAI_API_KEY",
    "TWITTER_AUTH_CONFIG_ID",
    "USER_ID",
    "SGAI_API_KEY",
    "NEBIUS_API_KEY",
]

missing_vars = [var for var in required_vars if not os.getenv(var)]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {missing_vars}")

print("🤖 Setting up Twitter Post Agent...")

# Initialize clients
composio = Composio()
openai_client = OpenAI()
scraper_tool = SmartScraperTool(api_key=os.getenv("SGAI_API_KEY"))
nebius_chat = ChatNebius(
    api_key=os.getenv("NEBIUS_API_KEY"),
    model="zai-org/GLM-4.5-Air",
    temperature=0.6,
    top_p=0.95,
)


# Initialize Memori
def initialize_memori():
    """Initialize Memori memory system for Twitter style"""
    try:
        memory_system = Memori(
            database_connect="sqlite:///tmp/twitter_style_memory.db",
            auto_ingest=True,
            conscious_ingest=True,
            verbose=False,
            namespace="twitter_tweeting_style",
        )
        memory_system.enable()
        return memory_system
    except Exception as e:
        raise Exception(f"Failed to initialize Memori: {e}")


# Create memory tool
def create_memory_tool_instance(memory_system):
    """Create memory tool instance"""
    return create_memory_tool(memory_system)


def scrape_user_tweets(twitter_handle: str) -> List[Dict[str, Any]]:
    """Scrape user's tweets using ScrapeGraph"""
    try:
        # Remove @ if present
        if twitter_handle.startswith("@"):
            twitter_handle = twitter_handle[1:]

        twitter_url = f"https://x.com/{twitter_handle}"

        # Initialize scraper tool fresh to get latest environment variables
        fresh_scraper_tool = SmartScraperTool(api_key=os.getenv("SGAI_API_KEY"))

        result = fresh_scraper_tool.invoke(
            {
                "website_url": twitter_url,
                "user_prompt": (
                    "Extract the following information for this Twitter handle: "
                    "- Username (display name)\n"
                    "- Profile image URL\n"
                    "- Handle (e.g., @username)\n"
                    "- The latest 10 top tweets (original tweets only, not replies, retweets, or quotes)\n"
                    "For each tweet, include: tweet text, timestamp, and any media URLs if available."
                ),
            }
        )

        # Return all details in a dictionary
        tweets = result.get("latest_tweets") or result.get("tweets")
        if tweets is None:
            raise Exception(f"No tweets found in result: {result}")

        print(
            {
                "username": result.get("username"),
                "profile_image_url": result.get("profile_image_url"),
                "handle": result.get("handle"),
                "tweets": tweets,
            }
        )
        return {
            "username": result.get("username"),
            "profile_image_url": result.get("profile_image_url"),
            "handle": result.get("handle"),
            "tweets": tweets,
        }

    except Exception as e:
        raise Exception(f"Error scraping tweets: {e}")


def render_tweet_card(username, handle, profile_image_url, tweet_text):
    """Render a tweet card HTML with dynamic profile, handle, and tweet text."""
    tweet_card_html = f'''
        <div
            style="background:#000;color:#E7E9EA;font-family:system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;max-width:720px;margin:16px 0 16px 0;padding:16px 20px;border:1px solid #2f3336;border-radius:16px;text-align:left;"
        >
            <div style="display:flex; align-items:flex-start; justify-content:space-between;">
                <div style="display:flex; align-items:center; gap:12px;">
                    <img
                        src="{profile_image_url}"
                        alt="User avatar"
                        width="48"
                        height="48"
                        style="border-radius:9999px; display:block;"
                    />
                    <div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <span style="color:#fff; font-weight:700; font-size:18px; line-height:1.2;">{username}</span>
                            <span aria-label="Verified" title="Verified" style="background:#1d9bf0;color:#fff;display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:9999px;font-size:12px;line-height:1;font-weight:700;">✓</span>
                        </div>
                        <div style="color:#8b98a5; font-size:14px; margin-top:2px;">{handle}</div>
                    </div>
                </div>
                <button type="button" style="background:#e6ecf0;color:#0f1419;border:0;padding:10px 16px;border-radius:9999px;font-weight:700;font-size:16px;cursor:pointer;">Promote</button>
            </div>
            <p style="color:#fff;font-size:26px;font-weight:400;line-height:1.3;margin:14px 0 12px;">{tweet_text}</p>

        </div>
        '''
    return tweet_card_html


def analyze_tweeting_style(tweets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze tweeting style using Nebius LLM"""
    try:
        # Prepare tweets for analysis
        tweets_text = ""
        for i, tweet in enumerate(tweets, 1):
            tweets_text += f"Tweet {i}: {tweet.get('description', 'N/A')}\n"

        prompt = f"""
        Analyze the following tweets and extract the author's tweeting style characteristics.
        Focus on:
        1. Tone (casual, professional, humorous, serious, etc.)
        2. Language style (formal, informal, slang, technical, etc.)
        3. Common hashtags and their themes
        4. Emoji usage patterns
        5. Tweet structure and length preferences
        6. Topics and interests they tweet about
        7. Writing personality and voice
        8. Common phrases or expressions they use

        Tweets to analyze:
        {tweets_text}

        Provide your analysis in JSON format with these keys:
        - tone: string describing the tone
        - language_style: string describing language formality and style
        - hashtag_patterns: list of common hashtags and themes
        - emoji_usage: string describing emoji patterns
        - tweet_structure: string describing tweet length and structure preferences
        - common_topics: list of topics they tweet about
        - personality: string describing overall personality
        - common_phrases: list of phrases or expressions they use
        - writing_habits: list of specific tweeting habits or patterns
        """

        response = nebius_chat.invoke(prompt)

        # Extract JSON from response
        analysis_text = response.content
        try:
            # Find JSON content between ```json and ``` markers
            if "```json" in analysis_text:
                json_start = analysis_text.find("```json") + 7
                json_end = analysis_text.find("```", json_start)
                json_content = analysis_text[json_start:json_end].strip()
            else:
                # Try to find JSON content
                json_start = analysis_text.find("{")
                json_end = analysis_text.rfind("}") + 1
                json_content = analysis_text[json_start:json_end]

            return json.loads(json_content)
        except:
            # Fallback: create structured response
            return {
                "tone": "Casual and engaging",
                "language_style": "Informal with some technical terms",
                "hashtag_patterns": ["#tech", "#AI", "#programming"],
                "emoji_usage": "Moderate use of emojis for emphasis",
                "tweet_structure": "Varied lengths, often includes links",
                "common_topics": ["Technology", "Programming", "AI"],
                "personality": "Tech-savvy and approachable",
                "common_phrases": ["Let me tell you", "Here's the thing"],
                "writing_habits": ["Uses hashtags", "Includes links", "Engaging tone"],
            }
    except Exception as e:
        raise Exception(f"Error analyzing tweeting style: {e}")


def store_tweeting_style_in_memori(
    memory_system,
    style_analysis: Dict[str, Any],
    twitter_handle: str,
    profile_image_url: str,
    handle: str,
    username: str,
):
    """Store tweeting style analysis in Memori"""
    try:
        hashtag_patterns = style_analysis.get("hashtag_patterns", [])
        hashtag_text = (
            ", ".join(hashtag_patterns[:3]) if hashtag_patterns else "various topics"
        )

        # Create a conversation about the tweeting style
        user_input = f"Hi AI, here is my Twitter style from @{twitter_handle}: {style_analysis.get('tone', 'N/A')} tone, {style_analysis.get('personality', 'N/A')} personality, {style_analysis.get('language_style', 'N/A')} language style."

        ai_response = f"I understand your Twitter style! You tweet with a {style_analysis.get('tone', 'N/A')} tone and {style_analysis.get('personality', 'N/A')} personality. Your language is {style_analysis.get('language_style', 'N/A')}. I'll use this to generate tweets that sound exactly like you."

        # Record the conversation in memory
        memory_system.record_conversation(
            user_input=user_input,
            ai_output=ai_response,
            model="nebius-glm-4.5-air",
            metadata={
                "type": "twitter_style_profile",
                "twitter_handle": twitter_handle,
                "style_data": style_analysis,
                "analysis_timestamp": "now",
                "profile_image_url": profile_image_url,
                "username": username,
                "handle": handle,
            },
        )

        return ai_response

    except Exception as e:
        raise Exception(f"Error storing in memory: {e}")


def generate_tweet_with_style(memory_tool, topic: str) -> str:
    """Generate tweet using stored tweeting style from memory"""
    try:
        # Get tweeting style context from memory
        writing_style_context = ""
        try:
            context_result = memory_tool.execute(query="twitter style tone personality")
            print(f"🧠 Memory search result: {context_result}")

            if context_result and "No relevant memories found" not in str(
                context_result
            ):
                writing_style_context = str(context_result)[:300]  # Shorter context
                print(
                    f"✅ Using stored Twitter style: {writing_style_context[:100]}..."
                )
            else:
                print("⚠️  No stored Twitter style found - using default style")
        except Exception as e:
            print(f"❌ Error accessing memory: {e}")
            pass  # Continue without context if search fails

        # Create appropriate prompt based on whether we have tweeting style
        if writing_style_context:
            prompt = f"Write a tweet about '{topic}' in this exact style: {writing_style_context}. Keep it casual, under 275 characters. NO quotes. Just the tweet."
        else:
            prompt = f"Write a casual tweet about '{topic}'. Under 275 characters. NO quotes. Just the tweet."

        response = nebius_chat.invoke(prompt)
        tweet_content = response.content.strip()

        # Clean up common formatting issues
        if tweet_content.startswith('"') and tweet_content.endswith('"'):
            tweet_content = tweet_content[1:-1]

        # Ensure it's under character limit
        if len(tweet_content) > 275:
            tweet_content = tweet_content[:275] + "..."

        print(f"📏 Generated tweet ({len(tweet_content)} chars): {tweet_content}")
        return tweet_content

    except Exception as e:
        raise Exception(f"Error generating tweet: {e}")


def post_tweet_via_composio(tweet_text: str) -> bool:
    """Post tweet using Composio Twitter toolkit - using the working create_tweet function"""
    try:
        # Use the imported create_tweet function
        print(f"🐦 Attempting to post tweet: {tweet_text[:50]}...")
        success = create_tweet(tweet_text)
        print(f"✅ Tweet posting result: {success}")
        return success

    except Exception as e:
        print(f"❌ Error posting tweet: {e}")
        return False


def get_stored_tweeting_style(memory_tool):
    """Retrieve stored tweeting style profile from memory"""
    try:
        queries = [
            "twitter style tone personality",
            "tweeting style analysis",
            "style profile hashtags",
            "twitter characteristics",
        ]

        for query in queries:
            try:
                result = memory_tool.execute(query=query.strip())
                if result and "No relevant memories found" not in str(result):
                    return result
            except Exception:
                continue

        return None
    except Exception as e:
        raise Exception(f"Error retrieving tweeting style: {e}")


def save_generated_tweet(memory_system, topic: str, tweet_content: str):
    """Save generated tweet content to memory"""
    try:
        memory_system.record_conversation(
            user_input=f"Generated tweet about: {topic}",
            ai_output=tweet_content,
            model="nebius-glm-4.5-air",
            metadata={
                "type": "generated_tweet",
                "topic": topic,
                "word_count": len(tweet_content.split()),
                "generated_timestamp": "now",
            },
        )
        return True
    except Exception as e:
        raise Exception(f"Error saving tweet to memory: {e}")