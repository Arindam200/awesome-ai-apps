#!/usr/bin/env python3
"""Initialize task management database"""

import asyncio
import asyncpg
import os
from pathlib import Path

async def init_database():
    # Database connection
    database_url = os.getenv('DATABASE_URL', 'postgresql://ai_apps:ai_apps_password@localhost:5432/ai_apps_tasks')

    try:
        conn = await asyncpg.connect(database_url)

        # Create tables
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                task_id VARCHAR(255) UNIQUE NOT NULL,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                category VARCHAR(100),
                priority VARCHAR(20),
                status VARCHAR(20) DEFAULT 'open',
                assignee VARCHAR(100),
                parent_task_id VARCHAR(255),
                github_issue_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                due_date TIMESTAMP,
                completed_at TIMESTAMP
            );
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS task_followups (
                id SERIAL PRIMARY KEY,
                parent_task_id VARCHAR(255) NOT NULL,
                followup_task_id VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_task_id) REFERENCES tasks(task_id),
                FOREIGN KEY (followup_task_id) REFERENCES tasks(task_id)
            );
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS deployments (
                id SERIAL PRIMARY KEY,
                deployment_id VARCHAR(255) UNIQUE NOT NULL,
                app_name VARCHAR(255) NOT NULL,
                environment VARCHAR(50) NOT NULL,
                version VARCHAR(100),
                status VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );
        ''')

        await conn.execute('''
            CREATE TABLE IF NOT EXISTS health_checks (
                id SERIAL PRIMARY KEY,
                app_name VARCHAR(255) NOT NULL,
                status VARCHAR(20) NOT NULL,
                response_time_ms INTEGER,
                error_message TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')

        print("✅ Database tables created successfully")
        await conn.close()

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(init_database())
