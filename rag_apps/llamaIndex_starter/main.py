import os
from llama_index.llms.nebius import NebiusLLM
from llama_index.core.llms import ChatMessage

def main():
    # Initialize the LLM
    # You can set the API key in environment variable or pass it directly
    # os.environ["NEBIUS_API_KEY"] = "your_api_key"
    
    llm = NebiusLLM(
        model="Qwen/Qwen3-235B-A22B",
        api_key=os.getenv("NEBIUS_API_KEY")
    )

    # Example 1: Basic completion
    print("\n=== Basic Completion Example ===")
    response = llm.complete("Who is Paul Graham?")
    print(response)

    # Example 2: Chat interface
    print("\n=== Chat Interface Example ===")
    messages = [
        ChatMessage(
            role="system",
            content="You are a pirate with a colorful personality"
        ),
        ChatMessage(role="user", content="What is your name?"),
    ]
    chat_response = llm.chat(messages)
    print(chat_response)

    # Example 3: Streaming completion
    print("\n=== Streaming Completion Example ===")
    print("Streaming response for 'Who is Paul Graham?':")
    for chunk in llm.stream_complete("Who is Paul Graham?"):
        print(chunk.delta, end="")

    # Example 4: Streaming chat
    print("\n\n=== Streaming Chat Example ===")
    print("Streaming chat response:")
    for chunk in llm.stream_chat(messages):
        print(chunk.delta, end="")

if __name__ == "__main__":
    main()