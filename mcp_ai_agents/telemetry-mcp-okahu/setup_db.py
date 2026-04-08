import sqlite3
import os

def setup_db():
    db_path = "sales.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
    CREATE TABLE users (
        user_id INTEGER PRIMARY KEY,
        username TEXT NOT NULL,
        email TEXT UNIQUE
    )
    """)
    
    cursor.execute("""
    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        order_date TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    """)
    
    # Seed data
    users = [
        (1, 'Alice', 'alice@example.com'),
        (2, 'Bob', 'bob@example.com'),
        (3, 'Charlie', 'charlie@example.com'),
        (4, 'David', 'david@example.com'),
        (5, 'Eve', 'eve@example.com')
    ]
    
    orders = [
        (101, 1, 150.00, '2024-03-01'), (102, 1, 85.50, '2024-03-05'),
        (103, 2, 200.00, '2024-03-10'), (104, 2, 45.00, '2024-03-12'),
        (105, 3, 120.00, '2024-03-15'), (106, 3, 300.25, '2024-03-18'),
        (107, 4, 15.99, '2024-03-20'), (108, 4, 55.00, '2024-03-22'),
        (109, 5, 99.99, '2024-03-25'), (110, 5, 10.50, '2024-03-26'),
        (111, 1, 25.00, '2024-03-27'), (112, 2, 75.20, '2024-03-28'),
        (113, 3, 18.00, '2024-03-29'), (114, 4, 220.00, '2024-03-30'),
        (115, 5, 42.00, '2024-03-31'), (116, 1, 130.00, '2024-04-01'),
        (117, 2, 60.00, '2024-04-02'), (118, 3, 90.00, '2024-04-03'),
        (119, 4, 110.00, '2024-04-04'), (120, 5, 20.00, '2024-04-05')
    ]
    
    cursor.executemany("INSERT INTO users VALUES (?, ?, ?)", users)
    cursor.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", orders)
    
    conn.commit()
    conn.close()
    print("Database sales.db created and seeded successfully.")

if __name__ == "__main__":
    setup_db()
