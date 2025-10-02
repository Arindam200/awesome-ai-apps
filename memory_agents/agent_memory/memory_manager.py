# memory_manager.py
from short_term_memory import ShortTermMemory
from long_term_memory import LongTermMemory

class MemoryManager:
    def __init__(self, long_term_db):
        self.short_term_memory = ShortTermMemory()
        self.long_term_memory = LongTermMemory(long_term_db)

    def remember(self, key, value, short_term=False):
        if short_term:
            self.short_term_memory.remember(key, value)
        else:
            self.long_term_memory.store(key, value)

    def recall(self, key, short_term=False):
        if short_term:
            return self.short_term_memory.recall(key)
        else:
            return self.long_term_memory.retrieve(key)

    def clear_short_term(self):
        self.short_term_memory.clear()

    def clear_long_term(self, key):
        self.long_term_memory.remove(key)
