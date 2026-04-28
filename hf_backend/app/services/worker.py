import asyncio
import os
import subprocess
import re
import shutil
from app.core.config import settings
from app.db import crud
from custom_logger import logger_config as logger

_worker_task = None

async def start_worker():
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(worker_loop())
        logger.info("TTS Worker background task started")

def is_worker_running():
    return _worker_task is not None and not _worker_task.done()

async def worker_loop():
    global _worker_task
    logger.info("TTS Worker loop started. Monitoring for new tasks...")
    
    while True:
        try:
            # Cleanup old entries
            await crud.cleanup_old_entries()
            
            # Get next unprocessed task
            task = await crud.get_next_not_started()
            
            if task:
                task_id = task['id']
                text = task['text']
                filename = task['filename']
                voice = task['voice'] or '4'
                speed = task['speed'] or 1.0
                
                logger.info(f"\n{'='*60}\nProcessing: {filename}\nID: {task_id}\n{'='*60}")
                await crud.update_status(task_id, 'processing')
                
                try:
                    await crud.update_progress(task_id, 5, "Initializing TTS...")
                    
                    # Write text to content.txt
                    content_path = os.path.join(settings.CWD, 'content.txt')
                    with open(content_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                    
                    # Run TTS command
                    command = [
                        settings.PYTHON_PATH, "-m", "tts_runner.runner",
                        "--model", "chatterbox",
                        "--voice", str(voice),
                        "--speed", str(speed)
                    ]
                    
                    logger.debug(f"Executing command: {' '.join(command)}")
                    
                    process = await asyncio.create_subprocess_exec(
                        *command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        cwd=settings.CWD,
                        env={
                            **os.environ,
                            'PYTHONUNBUFFERED': '1',
                            'CUDA_LAUNCH_BLOCKING': '1'
                        }
                    )
                    
                    total_sentences = 0
                    current_sentence = 0
                    
                    async for line in process.stdout:
                        line_str = line.decode('utf-8', errors='replace').strip()
                        if line_str:
                            logger.info(f"[TTS] {line_str}")
                            
                            # Parse "Processing X text sentences"
                            total_match = re.search(r'Processing\s+(\d+)\s+text\s+sentences', line_str)
                            if total_match:
                                total_sentences = int(total_match.group(1))

                            # Parse "Sentence X processed" lines (handles both "X" and "X/Y" formats)
                            match = re.search(r'Sentence\s+(\d+)(?:/(\d+))?\s+processed', line_str)
                            if match:
                                current_sentence = int(match.group(1))
                                if match.group(2):
                                    total_sentences = int(match.group(2))
                                
                                if total_sentences > 0:
                                    # Progress scales from 10% (model loaded) to 90% (start of combining)
                                    progress = 10 + int((current_sentence / total_sentences) * 80)
                                    await crud.update_progress(task_id, min(progress, 90), f"Processing sentence {current_sentence}/{total_sentences}")
                            
                            # Parse "Sampling: X%" for granular progress
                            sampling_match = re.search(r'Sampling:\s+(\d+)%', line_str)
                            if sampling_match and total_sentences > 0:
                                sampling_pct = int(sampling_match.group(1))
                                progress = 10 + int((current_sentence / total_sentences) * 80) + int((sampling_pct / 100) * (1 / total_sentences) * 80)
                                await crud.update_progress(task_id, min(progress, 89), f"Synthesizing sentence {current_sentence + 1}/{total_sentences} ({sampling_pct}%)")
                            
                            # Parse "Combining X audio files"
                            combine_match = re.search(r'Combining\s+(\d+)\s+audio\s+files', line_str)
                            if combine_match:
                                total_sentences = int(combine_match.group(1))
                                await crud.update_progress(task_id, 90, "Combining audio files...")
                            
                            if 'Model loaded successfully' in line_str:
                                await crud.update_progress(task_id, 10, "Model ready, starting synthesis...")
                    
                    await process.wait()
                    
                    if process.returncode == 0:
                        output_filename = "output_audio.wav"
                        if os.path.exists(output_filename):
                            target_filename = f"{task_id}.wav"
                            target_path = os.path.join(settings.UPLOAD_FOLDER, target_filename)
                            shutil.move(output_filename, target_path)
                            
                            logger.success(f"Successfully processed: {filename}")
                            await crud.update_status(task_id, 'completed', output_file=target_filename)
                        else:
                            raise Exception("Output audio file not found")
                    else:
                        raise Exception(f"TTS process failed with return code {process.returncode}")
                        
                except Exception as e:
                    logger.error(f"Failed to process {filename}: {str(e)}")
                    await crud.update_status(task_id, 'failed', error=str(e))
            else:
                await asyncio.sleep(settings.POLL_INTERVAL)
                
        except Exception as e:
            logger.error(f"Worker error: {str(e)}")
            await asyncio.sleep(settings.POLL_INTERVAL)
