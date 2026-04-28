import os

class Config:
    PORT = int(os.environ.get('PORT', 7860))
    UPLOAD_FOLDER = 'uploads'
    TEMP_DIR = 'temp_dir'
    DATABASE_FILE = 'tts_results.db'
    ALLOWED_EXTENSIONS = {'txt', 'md', 'text'}
    
    CWD = "./"
    PYTHON_PATH = "python3"
    POLL_INTERVAL = 2
    
    # TTS Specifics
    RETENTION_DAYS = 10

settings = Config()

os.makedirs(settings.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(settings.TEMP_DIR, exist_ok=True)
