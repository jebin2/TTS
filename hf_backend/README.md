# TTS Text-to-Speech Generator

A Python-based text-to-speech service with a neobrutalist web interface. Generate audio from text using the Kokoro model and download the results.

## Features

- 📝 Text-to-Speech generation
- 🤖 Multiple voices and speeds
- 💾 SQLite database for queue management
- 🎨 Neobrutalist UI with smooth animations
- 🔄 Real-time status updates
- 📱 Fully responsive design

## Project Structure

```
TTS/
├── hf_backend/
│   ├── app.py              # Flask API server & Worker
│   ├── index.html          # Frontend UI
│   ├── requirements.txt    # Python dependencies
│   └── Dockerfile          # Docker configuration
├── tts_runner/             # TTS Logic Package
└── setup.py                # Package setup
```

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r hf_backend/requirements.txt
```

### 2. Start the Server

```bash
cd hf_backend
python app.py
```

The server will start on `http://localhost:7860` (or the port specified by PORT env var).
The background worker starts automatically with the server.

### 3. Access the Web Interface

Open your browser and navigate to:
```
http://localhost:7860
```

## Usage

### Via Web Interface

1. Enter text in the textarea
2. Select a voice and speed
3. Click "Generate Audio"
4. Watch the status update in real-time
5. Download the generated audio once processing completes

### Via API

**Generate Audio:**
```bash
curl -X POST http://localhost:7860/api/generate \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello world", "voice": "8", "speed": 1.0}'
```

**Get All Tasks:**
```bash
curl http://localhost:7860/api/files
```

**Download Audio:**
```bash
curl -O http://localhost:7860/api/download/<task_id>
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/generate` | POST | Queue a new TTS task |
| `/api/files` | GET | Get all tasks and statuses |
| `/api/download/<id>` | GET | Download generated audio |

## Database Schema

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    voice TEXT,
    speed REAL,
    status TEXT NOT NULL,
    output_file TEXT,
    created_at TEXT NOT NULL,
    processed_at TEXT,
    error TEXT
);
```

## Status Values

- `not_started` - Task queued, waiting for processing
- `processing` - Currently generating audio
- `completed` - Successfully generated
- `failed` - Error during generation

## Tech Stack

- **Backend:** Flask (Python)
- **Database:** SQLite
- **Frontend:** Vanilla HTML/CSS/JavaScript
- **TTS:** Kokoro (via tts_runner)
- **Design:** Neobrutalism with neon accents

## License

MIT