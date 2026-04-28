from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import os
import uuid
import aiofiles
from app.core.config import settings
from custom_logger import logger_config as logger
from app.db import crud
from app.services.worker import start_worker, is_worker_running

router = APIRouter()

@router.get("/")
async def index():
    return FileResponse('index.html')

@router.post("/api/tasks/upload")
async def create_task(
    text: str = Form(None),
    file: UploadFile = File(None),
    voice: str = Form("4"),
    speed: float = Form(1.0),
    hide_from_ui: str = Form("")
):
    task_text = ""
    
    if text:
        task_text = text
    elif file:
        try:
            content = await file.read()
            task_text = content.decode('utf-8')
        except Exception as e:
            logger.error(f"Error reading uploaded file: {e}")
            raise HTTPException(status_code=400, detail="Could not read file content")
    
    if not task_text.strip():
        raise HTTPException(status_code=400, detail="No text provided")
    
    task_id = str(uuid.uuid4())
    filename = file.filename if file else f"{task_text[:20]}..."
    hide_from_ui_val = 1 if hide_from_ui.lower() in ['true', '1'] else 0
    
    await crud.insert_task(task_id, filename, task_text, voice, speed, 'not_started', hide_from_ui_val)
    await start_worker()
    
    return JSONResponse(status_code=201, content={
        'id': task_id,
        'filename': filename,
        'status': 'not_started',
        'message': 'Task created successfully'
    })

@router.get("/api/tasks")
async def get_tasks():
    rows, queue_ids, processing_count, avg_time = await crud.get_all_tasks()
    
    tasks = []
    for row in rows:
        queue_position = None
        estimated_start_seconds = None
        
        if row['status'] == 'not_started' and row['id'] in queue_ids:
            queue_position = queue_ids.index(row['id']) + 1
            tasks_ahead = queue_position - 1 + processing_count
            estimated_start_seconds = round(tasks_ahead * avg_time)
        
        tasks.append({
            'id': row['id'],
            'filename': row['filename'],
            'status': row['status'],
            'result': "HIDDEN_IN_LIST_VIEW",
            'created_at': row['created_at'],
            'processed_at': row['processed_at'],
            'progress': row['progress'] or 0,
            'progress_text': row['progress_text'],
            'queue_position': queue_position,
            'estimated_start_seconds': estimated_start_seconds
        })
    
    return tasks

@router.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    result = await crud.get_task_by_id(task_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
        
    row, queue_position, estimated_start_seconds = result
    
    return {
        'id': row['id'],
        'filename': row['filename'],
        'text': row['text'],
        'status': row['status'],
        'result': row['text'], # result maps to text for detail view
        'output_file': row['output_file'],
        'created_at': row['created_at'],
        'processed_at': row['processed_at'],
        'progress': row['progress'] or 0,
        'progress_text': row['progress_text'],
        'queue_position': queue_position,
        'estimated_start_seconds': estimated_start_seconds
    }

@router.get("/api/download/{task_id}")
async def download_task(task_id: str):
    result = await crud.get_task_by_id(task_id)
    if not result or not result[0]['output_file']:
        raise HTTPException(status_code=404, detail="Audio file not found")
        
    row = result[0]
    filepath = os.path.join(settings.UPLOAD_FOLDER, row['output_file'])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File missing on server")
        
    return FileResponse(filepath, media_type="audio/wav", filename=f"tts_{task_id}.wav")

@router.get("/health")
async def health():
    return {
        'status': 'healthy',
        'service': 'tts-runner',
        'worker_running': is_worker_running()
    }
