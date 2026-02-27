from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
import sqlite3
import os
import uuid
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import threading
import subprocess
import time
import shutil

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('temp_dir', exist_ok=True)

# Worker state
worker_thread = None
worker_running = False

# Cleanup settings
RETENTION_DAYS = 10  # Delete entries older than this many days

def init_db():
    conn = sqlite3.connect('tts_tasks.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tasks
                 (id TEXT PRIMARY KEY,
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

    conn.commit()
    conn.close()

def cleanup_old_entries():
    """Delete entries older than RETENTION_DAYS along with their audio files"""
    cutoff_date = (datetime.now() - timedelta(days=RETENTION_DAYS)).isoformat()
    
    print(f"\n🧹 Running cleanup for entries older than {RETENTION_DAYS} days...")
    
    try:
        conn = sqlite3.connect('tts_tasks.db')
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Find old entries
        c.execute('SELECT id, output_file FROM tasks WHERE created_at < ?', (cutoff_date,))
        old_entries = c.fetchall()
        
        if not old_entries:
            print("   No old entries to clean up.")
            conn.close()
            return
        
        deleted_count = 0
        for entry in old_entries:
            task_id = entry['id']
            output_file = entry['output_file']
            
            # Delete audio file if it exists
            if output_file:
                file_path = os.path.join(UPLOAD_FOLDER, output_file)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"   🗑️  Deleted audio: {output_file}")
            
            # Delete database entry
            c.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            deleted_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"   ✅ Cleaned up {deleted_count} old entries.\n")
        
    except Exception as e:
        print(f"   ⚠️  Cleanup error: {str(e)}\n")

def start_worker():
    """Start the worker thread if not already running"""
    global worker_thread, worker_running
    
    if not worker_running:
        worker_running = True
        worker_thread = threading.Thread(target=worker_loop, daemon=True)
        worker_thread.start()
        print("✅ Worker thread started")

def worker_loop():
    """Main worker loop that processes TTS tasks"""
    print("🤖 TTS Worker started. Monitoring for new tasks...")
    
    CWD = "./"
    PYTHON_PATH = "python3" # Or just python
    POLL_INTERVAL = 2  # seconds
    
    while worker_running:
        try:
            # Get next unprocessed task
            conn = sqlite3.connect('tts_tasks.db')
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute('''SELECT * FROM tasks 
                         WHERE status = 'not_started' 
                         ORDER BY created_at ASC 
                         LIMIT 1''')
            row = c.fetchone()
            conn.close()
            
            if row:
                task_id = row['id']
                text = row['text']
                voice = row['voice'] or '9' # Default voice index (bm_lewis)
                speed = row['speed'] or 1.0
                
                # Run cleanup before processing each task
                cleanup_old_entries()
                
                print(f"\n{'='*60}")
                print(f"🎵 Processing Task: {task_id}")
                print(f"📝 Text: {text[:50]}...")
                print(f"{'='*60}")
                
                # Update status to processing
                update_status(task_id, 'processing')
                
                try:
                    # Write text to content.txt
                    with open('content.txt', 'w', encoding='utf-8') as f:
                        f.write(text)
                    
                    # Run TTS command
                    # python3 -m tts_runner.runner --model kokoro --voice <voice> --speed <speed>
                    print(f"🔄 Running TTS...")
                    command = [
                        PYTHON_PATH, "-m", "tts_runner.runner",
                        "--model", "chatterbox",
                        "--voice", str(voice),
                        "--speed", str(speed)
                    ]
                    
                    # Run with output capture for progress tracking
                    import re
                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        cwd=CWD,
                        text=True,
                        bufsize=1,
                        env={
                            **os.environ,
                            'PYTHONUNBUFFERED': '1',
                            'CUDA_LAUNCH_BLOCKING': '1'
                        }
                    )
                    
                    total_sentences = 0
                    current_sentence = 0
                    
                    for line in process.stdout:
                        print(line, end='')  # Echo to console
                        
                        # Parse "Sentence X processed" lines
                        match = re.search(r'Sentence\s+(\d+)\s+processed', line)
                        if match:
                            current_sentence = int(match.group(1))
                            # Try to get total from "Combining X audio files"
                            if total_sentences > 0:
                                progress = int((current_sentence / total_sentences) * 100)
                                update_progress(task_id, progress, f"Processing sentence {current_sentence}/{total_sentences}")
                        
                        # Parse "Combining X audio files" to get total count
                        combine_match = re.search(r'Combining\s+(\d+)\s+audio\s+files', line)
                        if combine_match:
                            total_sentences = int(combine_match.group(1))
                            update_progress(task_id, 90, "Combining audio files...")
                        
                        # Parse "Processing text sentences..." as start
                        if 'Processing text sentences' in line:
                            update_progress(task_id, 5, "Processing text sentences...")
                        
                        # Parse model loading
                        if 'Model loaded successfully' in line:
                            update_progress(task_id, 10, "Model loaded, starting TTS...")
                    
                    process.wait()
                    if process.returncode != 0:
                        raise Exception(f"TTS process failed with return code {process.returncode}")
                    
                    # Check for output file
                    output_filename = "output_audio.wav"
                    if os.path.exists(output_filename):
                        # Move to uploads folder
                        target_filename = f"{task_id}.wav"
                        target_path = os.path.join(UPLOAD_FOLDER, target_filename)
                        shutil.move(output_filename, target_path)
                        
                        print(f"✅ Successfully processed: {target_filename}")
                        
                        # Update database with success
                        update_status(task_id, 'completed', output_file=target_filename)
                    else:
                        raise Exception("Output audio file not found")
                    
                except Exception as e:
                    print(f"❌ Failed to process: {task_id}")
                    print(f"Error: {str(e)}")
                    update_status(task_id, 'failed', error=str(e))
                    
            else:
                # No tasks to process, sleep for a bit
                time.sleep(POLL_INTERVAL)
                
        except Exception as e:
            print(f"⚠️  Worker error: {str(e)}")
            time.sleep(POLL_INTERVAL)

def update_progress(task_id, progress, progress_text=None):
    """Update the progress of a task"""
    conn = sqlite3.connect('tts_tasks.db')
    c = conn.cursor()
    c.execute('UPDATE tasks SET progress = ?, progress_text = ? WHERE id = ?',
              (progress, progress_text, task_id))
    conn.commit()
    conn.close()

def update_status(task_id, status, output_file=None, error=None):
    """Update the status of a task in the database"""
    conn = sqlite3.connect('tts_tasks.db')
    c = conn.cursor()
    
    if status == 'completed':
        c.execute('''UPDATE tasks 
                     SET status = ?, output_file = ?, processed_at = ?, progress = 100, progress_text = 'Completed'
                     WHERE id = ?''',
                  (status, output_file, datetime.now().isoformat(), task_id))
    elif status == 'failed':
        c.execute('''UPDATE tasks 
                     SET status = ?, error = ?, processed_at = ?, progress_text = 'Failed'
                     WHERE id = ?''',
                  (status, str(error), datetime.now().isoformat(), task_id))
    else:
        c.execute('UPDATE tasks SET status = ? WHERE id = ?', (status, task_id))
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/generate', methods=['POST'])
def generate_audio():
    data = request.json
    if not data or 'text' not in data:
        return jsonify({'error': 'No text provided'}), 400
    
    text = data['text']
    voice = data.get('voice', '9')
    speed = data.get('speed', 1.0)
    hide_from_ui = 1 if data.get('hide_from_ui') else 0
    
    if not text.strip():
        return jsonify({'error': 'Text cannot be empty'}), 400
    
    task_id = str(uuid.uuid4())
    
    conn = sqlite3.connect('tts_tasks.db')
    c = conn.cursor()
    c.execute('''INSERT INTO tasks 
                 (id, text, voice, speed, status, created_at, hide_from_ui)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (task_id, text, voice, speed, 'not_started', datetime.now().isoformat(), hide_from_ui))
    conn.commit()
    conn.close()
    
    # Start worker on first request
    start_worker()
    
    return jsonify({
        'id': task_id,
        'status': 'not_started',
        'message': 'Task queued successfully'
    }), 201

@app.route('/api/files', methods=['GET'])
def get_files():
    conn = sqlite3.connect('tts_tasks.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM tasks WHERE hide_from_ui = 0 OR hide_from_ui IS NULL ORDER BY created_at DESC')
    rows = c.fetchall()
    
    # Get queue order for not_started tasks (oldest first = position 1)
    c.execute('''SELECT id FROM tasks 
                 WHERE status = 'not_started' 
                 ORDER BY created_at ASC''')
    queue_order = [r['id'] for r in c.fetchall()]
    
    # Check if any task is currently processing
    c.execute('SELECT COUNT(*) as count FROM tasks WHERE status = "processing"')
    processing_count = c.fetchone()['count']
    
    conn.close()
    
    # Average processing time in seconds (can be adjusted based on actual metrics)
    AVG_PROCESSING_TIME = 30
    
    files = []
    for row in rows:
        file_data = {
            'id': row['id'],
            'text': row['text'],
            'status': row['status'],
            'output_file': row['output_file'],
            'created_at': row['created_at'],
            'processed_at': row['processed_at'],
            'error': row['error'],
            'progress': row['progress'] or 0,
            'progress_text': row['progress_text']
        }
        
        # Add queue position for not_started tasks
        if row['status'] == 'not_started' and row['id'] in queue_order:
            queue_position = queue_order.index(row['id']) + 1  # 1-indexed
            file_data['queue_position'] = queue_position
            # Estimated time = (position - 1 + processing_count) * avg_time
            # If something is processing, add that to the wait
            tasks_ahead = queue_position - 1 + processing_count
            file_data['estimated_start_seconds'] = tasks_ahead * AVG_PROCESSING_TIME
        
        files.append(file_data)
    
    return jsonify(files)

@app.route('/api/download/<task_id>', methods=['GET'])
def download_file(task_id):
    conn = sqlite3.connect('tts_tasks.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    row = c.fetchone()
    conn.close()
    
    if row is None or not row['output_file']:
        return jsonify({'error': 'File not found'}), 404
    
    file_path = os.path.join(UPLOAD_FOLDER, row['output_file'])
    if not os.path.exists(file_path):
        return jsonify({'error': 'File missing on server'}), 404
        
    return send_file(file_path, as_attachment=True, download_name=f"tts_{task_id}.wav")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'service': 'tts-generator',
        'worker_running': worker_running
    })

if __name__ == '__main__':
    init_db()
    print("\n" + "="*60)
    print("🚀 TTS Generator API Server")
    print("="*60)
    print("📌 Worker will start automatically on first request")
    print("="*60 + "\n")
    
    # Use PORT environment variable for Hugging Face compatibility
    port = int(os.environ.get('PORT', 7860))
    app.run(debug=False, host='0.0.0.0', port=port)