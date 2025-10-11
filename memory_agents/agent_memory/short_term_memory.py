# short_term_memory.py
class ShortTermMemory:
    def __init__(self):
        self.memory = {}

    def remember(self, key, value):
        self.memory[key] = value

    def recall(self, key):
        return self.memory.get(key, None)

    def clear(self):
        self.memory.clear()