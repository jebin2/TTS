import aiosqlite
import os
from datetime import datetime, timedelta
from app.core.config import settings
from custom_logger import logger_config as logger

async def insert_task(task_id: str, filename: str, text: str, voice: str, speed: float, status: str, hide_from_ui: int):
    async with aiosqlite.connect(settings.DATABASE_FILE) as db:
        await db.execute('''INSERT INTO tasks 
                     (id, filename, text, voice, speed, status, created_at, hide_from_ui)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (task_id, filename, text, voice, speed, status, datetime.now().isoformat(), hide_from_ui))
        await db.commit()
    logger.debug(f"Inserted task {task_id} into database.")

async def update_status(task_id: str, status: str, output_file: str = None, error: str = None):
    async with aiosqlite.connect(settings.DATABASE_FILE) as db:
        if status == 'completed':
            await db.execute('''UPDATE tasks 
                         SET status = ?, output_file = ?, processed_at = ?, progress = 100, progress_text = 'Completed'
                         WHERE id = ?''',
                      (status, output_file, datetime.now().isoformat(), task_id))
            logger.info(f"Task ID {task_id} marked as completed.")
        elif status == 'failed':
            await db.execute('''UPDATE tasks 
                         SET status = ?, error = ?, processed_at = ?, progress_text = 'Failed'
                         WHERE id = ?''',
                      (status, str(error), datetime.now().isoformat(), task_id))
            logger.error(f"Task ID {task_id} marked as failed. Error: {error}")
        else:
            await db.execute('UPDATE tasks SET status = ? WHERE id = ?', (status, task_id))
            logger.debug(f"Task ID {task_id} status updated to {status}.")
        await db.commit()

async def update_progress(task_id: str, progress: int, progress_text: str = None):
    async with aiosqlite.connect(settings.DATABASE_FILE) as db:
        await db.execute('UPDATE tasks SET progress = ?, progress_text = ? WHERE id = ?',
                  (progress, progress_text, task_id))
        await db.commit()
    logger.debug(f"Task ID {task_id} progress updated to {progress}% ({progress_text}).")

async def get_next_not_started():
    async with aiosqlite.connect(settings.DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''SELECT * FROM tasks 
                     WHERE status = 'not_started' 
                     ORDER BY created_at ASC 
                     LIMIT 1''') as cursor:
            return await cursor.fetchone()

async def cleanup_old_entries():
    try:
        async with aiosqlite.connect(settings.DATABASE_FILE) as db:
            db.row_factory = aiosqlite.Row
            cutoff_date = (datetime.now() - timedelta(days=settings.RETENTION_DAYS)).isoformat()
            
            async with db.execute('''SELECT id, output_file FROM tasks 
                         WHERE created_at < ?''', (cutoff_date,)) as cursor:
                old_entries = await cursor.fetchall()
            
            if old_entries:
                deleted_files = 0
                deleted_rows = 0
                
                for entry in old_entries:
                    output_file = entry['output_file']
                    if output_file:
                        filepath = os.path.join(settings.UPLOAD_FOLDER, output_file)
                        if os.path.exists(filepath):
                            try:
                                os.remove(filepath)
                                deleted_files += 1
                            except Exception as e:
                                logger.warning(f"Failed to delete old file {filepath}: {e}")
                
                async with db.execute('''DELETE FROM tasks WHERE created_at < ?''', (cutoff_date,)) as cursor:
                    deleted_rows = cursor.rowcount
                await db.commit()
                
                if deleted_rows > 0 or deleted_files > 0:
                    logger.info(f"Cleanup: Deleted {deleted_rows} old entries and {deleted_files} audio files")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

async def get_average_processing_time():
    async with aiosqlite.connect(settings.DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('''SELECT created_at, processed_at FROM tasks 
                          WHERE status = 'completed' AND processed_at IS NOT NULL
                          ORDER BY processed_at DESC LIMIT 20''') as cursor:
            completed_rows = await cursor.fetchall()
        
        if not completed_rows:
            return 30.0
        
        total_seconds = 0
        count = 0
        for r in completed_rows:
            try:
                created = datetime.fromisoformat(r['created_at'])
                processed = datetime.fromisoformat(r['processed_at'])
                duration = (processed - created).total_seconds()
                if duration > 0:
                    total_seconds += duration
                    count += 1
            except:
                continue
        
        return total_seconds / count if count > 0 else 30.0

async def get_all_tasks():
    async with aiosqlite.connect(settings.DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        
        avg_time = await get_average_processing_time()
        
        async with db.execute('''SELECT id FROM tasks 
                     WHERE status = 'not_started' 
                     ORDER BY created_at ASC''') as cursor:
            queue_ids = [row['id'] for row in await cursor.fetchall()]
        
        async with db.execute('''SELECT COUNT(*) as count FROM tasks WHERE status = 'processing' ''') as cursor:
            row = await cursor.fetchone()
            processing_count = row['count']
        
        async with db.execute('SELECT * FROM tasks WHERE hide_from_ui = 0 OR hide_from_ui IS NULL ORDER BY created_at DESC') as cursor:
            rows = await cursor.fetchall()
            
        return rows, queue_ids, processing_count, avg_time

async def get_task_by_id(task_id: str):
    async with aiosqlite.connect(settings.DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)) as cursor:
            row = await cursor.fetchone()
            
        if not row:
            return None
            
        queue_position = None
        estimated_start_seconds = None
        
        if row['status'] == 'not_started':
            avg_time = await get_average_processing_time()
            
            async with db.execute('''SELECT COUNT(*) as position FROM tasks 
                         WHERE status = 'not_started' AND created_at < ?''',
                      (row['created_at'],)) as cursor:
                position_row = await cursor.fetchone()
                queue_position = position_row['position'] + 1
            
            async with db.execute('''SELECT COUNT(*) as count FROM tasks WHERE status = 'processing' ''') as cursor:
                count_row = await cursor.fetchone()
                processing_count = count_row['count']
            
            tasks_ahead = queue_position - 1 + processing_count
            estimated_start_seconds = round(tasks_ahead * avg_time)
            
        return row, queue_position, estimated_start_seconds
