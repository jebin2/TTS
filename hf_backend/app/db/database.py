import aiosqlite
from app.core.config import settings
from custom_logger import logger_config as logger

async def init_db():
    logger.info(f"Initializing database at {settings.DATABASE_FILE}")
    async with aiosqlite.connect(settings.DATABASE_FILE) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS tasks
                     (id TEXT PRIMARY KEY,
                      filename TEXT,
                      text TEXT NOT NULL,
                      voice TEXT,
                      speed REAL,
                      status TEXT NOT NULL,
                      output_file TEXT,
                      created_at TEXT NOT NULL,
                      processed_at TEXT,
                      error TEXT,
                      progress INTEGER DEFAULT 0,
                      progress_text TEXT,
                      hide_from_ui INTEGER DEFAULT 0)'''
        )
        await db.commit()
    logger.info("Database initialized successfully.")
