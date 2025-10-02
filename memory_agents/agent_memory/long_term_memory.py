# long_term_memory.py
class LongTermMemory:
    def __init__(self, database):
        self.database = database  # Database for long-term storage

    def store(self, key, value):
        self.database[key] = value

    def retrieve(self, key):
        return self.database.get(key, None)

    def remove(self, key):
        if key in self.database:
            del self.database[key]
