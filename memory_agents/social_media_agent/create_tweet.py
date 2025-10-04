import os

from composio import Composio
from dotenv import load_dotenv
from openai import OpenAI
load_dotenv()


def create_tweet(tweet_text):
    """
    Create a tweet using Composio's Twitter toolkit
    """
    # Initialize clients
    composio = Composio()
    openai_client = OpenAI()

    # Get configuration from environment
    user_id = os.getenv("USER_ID")
    auth_config_id = os.getenv("TWITTER_AUTH_CONFIG_ID")

    if not user_id or not auth_config_id:
        print("❌ Please set USER_ID and TWITTER_AUTH_CONFIG_ID in your .env file")
        return False

    try:
        # Get Twitter tools
        tools = composio.tools.get(user_id=user_id, toolkits=["TWITTER"])
        print(f"✅ Found {len(tools)} Twitter tools")

        # Use OpenAI to create the tweet
        completion = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": f"Create a tweet with this text: '{tweet_text}'",
                },
            ],
            tools=tools,
        )

        # Execute the tool call
        if completion.choices[0].message.tool_calls:
            result = composio.provider.handle_tool_calls(
                user_id=user_id, response=completion
            )
            print(f"✅ Tweet created successfully!")
            print(f"Result: {result}")
            return True
        else:
            print("❌ No tool calls were made")
            return False

    except Exception as e:
        print(f"❌ Error creating tweet: {e}")
        return False


# if __name__ == "__main__":
#     # Example tweet text
#     tweet_text = "Hello from Composio! 🚀 #AI #Twitter"

#     print(f"🐦 Creating tweet: {tweet_text}")
#     print("=" * 50)

#     success = create_tweet(tweet_text)

#     if success:
#         print("\n🎉 Tweet posted successfully!")
#         print("Check your Twitter account to see the new tweet.")
#     else:
#         print("\n❌ Failed to post tweet. Check the error messages above.")