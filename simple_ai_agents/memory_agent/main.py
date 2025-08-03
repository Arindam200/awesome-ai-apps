from agno.agent import Agent
from agno.memory.v2.db.sqlite import SqliteMemoryDb
from agno.memory.v2.memory import Memory
from agno.models.nebius import Nebius
from agno.storage.sqlite import SqliteStorage
from rich.pretty import pprint
import os
from dotenv import load_dotenv

load_dotenv()


# UserId for the memories
user_id = "arindam"
# Database file for memory and storage
db_file = "tmp/agent.db"

# Initialize memory.v2
memory = Memory(
    # Use any model for creating memories
    model=Nebius(
        id="deepseek-ai/DeepSeek-V3-0324", api_key=os.getenv("NEBIUS_API_KEY")
    ),
    db=SqliteMemoryDb(table_name="user_memories", db_file=db_file),
)
# Initialize storage
storage = SqliteStorage(table_name="agent_sessions", db_file=db_file)

# Initialize Agent
memory_agent = Agent(
    model=Nebius(
        id="deepseek-ai/DeepSeek-V3-0324", api_key=os.getenv("NEBIUS_API_KEY")
    ),
    # Store memories in a database
    memory=memory,
    # Give the Agent the ability to update memories
    enable_agentic_memory=True,
    # OR - Run the MemoryManager after each response
    enable_user_memories=True,
    # Store the chat history in the database
    storage=storage,
    # Add the chat history to the messages
    add_history_to_messages=True,
    # Number of history runs
    num_history_runs=3,
    markdown=True,
)

memory.clear()
memory_agent.print_response(
    "My name is Arindam and I support Mohun Bagan.",
    user_id=user_id,
    stream=True,
    stream_intermediate_steps=True,
)
print("Memories about Arindam:")
pprint(memory.get_user_memories(user_id=user_id))

memory_agent.print_response(
    "I live in Kolkata, where should i move within a 4 hour drive?",
    user_id=user_id,
    stream=True,
    stream_intermediate_steps=True,
)
print("Memories about Arindam:")
pprint(memory.get_user_memories(user_id=user_id))

memory_agent.print_response(
    "Tell me about Arindam",
    user_id=user_id,
    stream=True,
    stream_intermediate_steps=True,
)
print("Memories about Arindam:")
pprint(memory.get_user_memories(user_id=user_id))
