# TTS Text-to-Speech Generator

A Python-based text-to-speech service with a neobrutalist web interface. Upload text files via API, process them with TTS (Text-to-Speech), and view results in a stunning UI.

## Features

- 🎵 Text file upload via REST API
- 🤖 Automatic TTS processing using kokoro
- 💾 SQLite database for queue management
- 🎨 Neobrutalist UI with smooth animations
- 🔄 Real-time status updates
- 📱 Fully responsive design

## Project Structure

```
audio-caption-project/
├── app.py              # Flask API server
├── worker.py           # Background STT processing service
├── index.html          # Frontend UI
├── requirements.txt    # Python dependencies
├── audio_captions.db   # SQLite database (auto-created)
└── uploads/            # Uploaded audio files (auto-created)
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Up TTS Tool

Make sure you have the `kokoro` tool available in your PATH or current directory. This should be the kokoro based transcription tool.

### 3. Start the API Server

```bash
python app.py
```

The server will start on `http://localhost:5000`

### 4. Start the Background Worker

In a separate terminal:

```bash
python worker.py
```

The worker will poll the database every 5 seconds for new files to process.

### 5. Access the Web Interface

Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

### Via Web Interface

1. Click or drag-and-drop a text file onto the upload zone
2. Click "Upload & Process"
3. Watch the status update in real-time
4. View the generated caption once processing completes

### Via API

**Upload Text File:**
```bash
curl -X POST http://localhost:5000/api/upload \
  -F "audio=@/path/to/your/audio.wav"
```

**Get All Files:**
```bash
curl http://localhost:5000/api/files
```

**Get Specific File:**
```bash
curl http://localhost:5000/api/files/<file_id>
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload text file |
| `/api/files` | GET | Get all files |
| `/api/files/<id>` | GET | Get specific file |

## Database Schema

```sql
CREATE TABLE tts_files (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,
    status TEXT NOT NULL,
    caption TEXT,
    created_at TEXT NOT NULL,
    processed_at TEXT
);
```

## Status Values

- `not_started` - File uploaded, waiting for processing
- `processing` - Currently being transcribed
- `completed` - Successfully transcribed
- `failed` - Error during transcription

## Configuration

Edit these variables in `worker.py` to customize:

```python
CWD = "./"                          # Working directory
PYTHON_PATH = "kokoro"      # Path to TTS tool
POLL_INTERVAL = 5                    # Polling interval in seconds
```

## Supported Audio Formats

- WAV
- MP3
- FLAC
- OGG
- M4A
- AAC

## Troubleshooting

**Worker not processing files:**
- Ensure the `kokoro` tool is properly installed
- Check that the temp_dir exists for output
- Verify the audio file path is correct

**CORS errors:**
- Make sure flask-cors is installed
- Check that the API server is running

**Database errors:**
- Delete `tts_files.db` and restart the API server to recreate it

## Tech Stack

- **Backend:** Flask (Python)
- **Database:** SQLite
- **Frontend:** Vanilla HTML/CSS/JavaScript
- **TTS:** kokoro
- **Design:** Neobrutalism with neon accents

## License

MIT