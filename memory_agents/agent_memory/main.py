# main.py
from memory_manager import MemoryManager

# Example of a long-term memory database (could be replaced with a database system)
long_term_db = {}

# Initialize memory manager
memory_manager = MemoryManager(long_term_db)

# Storing and recalling short-term memory
memory_manager.remember('user_name', 'John', short_term=True)
print("Short-term memory: ", memory_manager.recall('user_name', short_term=True))  # Output: John

# Storing and recalling long-term memory
memory_manager.remember('user_preferences', {'theme': 'dark', 'notifications': 'enabled'}, short_term=False)
print("Long-term memory: ", memory_manager.recall('user_preferences', short_term=False))  # Output: {'theme': 'dark', 'notifications': 'enabled'}

# Clearing short-term memory
memory_manager.clear_short_term()

# After clearing, short-term memory is no longer available
print("After clearing short-term memory: ", memory_manager.recall('user_name', short_term=True))  # Output: None
