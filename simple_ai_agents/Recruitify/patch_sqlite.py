import sys
import os

__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')