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
| `/health` | GET | Check service health status |

---

### POST `/api/generate`

Queue a new text-to-speech generation task.

**Request Body:**
```json
{
  "text": "Hello, this is a sample text to convert to speech.",
  "voice": "8",
  "speed": 1.0
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `text` | string | Yes | - | The text to convert to speech. Cannot be empty. |
| `voice` | string | No | `"8"` | Voice ID to use for generation. |
| `speed` | number | No | `1.0` | Speech speed multiplier. |

**Success Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "not_started",
  "message": "Task queued successfully"
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "No text provided"
}
```
```json
{
  "error": "Text cannot be empty"
}
```

---

### GET `/api/files`

Retrieve all TTS tasks and their statuses, ordered by creation date (newest first).

**Request:** No parameters required.

**Success Response (200 OK):**
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "text": "Hello world",
    "status": "completed",
    "output_file": "550e8400-e29b-41d4-a716-446655440000.wav",
    "created_at": "2024-01-15T10:30:00.000000",
    "processed_at": "2024-01-15T10:30:05.000000",
    "error": null
  },
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "text": "Processing example",
    "status": "processing",
    "output_file": null,
    "created_at": "2024-01-15T10:31:00.000000",
    "processed_at": null,
    "error": null
  },
  {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "text": "Queued example",
    "status": "not_started",
    "output_file": null,
    "created_at": "2024-01-15T10:33:00.000000",
    "processed_at": null,
    "error": null,
    "queue_position": 1,
    "estimated_start_seconds": 30
  },
  {
    "id": "880e8400-e29b-41d4-a716-446655440003",
    "text": "Second in queue",
    "status": "not_started",
    "output_file": null,
    "created_at": "2024-01-15T10:34:00.000000",
    "processed_at": null,
    "error": null,
    "queue_position": 2,
    "estimated_start_seconds": 60
  },
  {
    "id": "990e8400-e29b-41d4-a716-446655440004",
    "text": "Failed example",
    "status": "failed",
    "output_file": null,
    "created_at": "2024-01-15T10:32:00.000000",
    "processed_at": "2024-01-15T10:32:10.000000",
    "error": "Output audio file not found"
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique task identifier (UUID). |
| `text` | string | Original text submitted for conversion. |
| `status` | string | Current task status (`not_started`, `processing`, `completed`, `failed`). |
| `output_file` | string \| null | Filename of generated audio (null if not completed). |
| `created_at` | string | ISO 8601 timestamp when task was created. |
| `processed_at` | string \| null | ISO 8601 timestamp when processing finished (null if not processed). |
| `error` | string \| null | Error message if task failed (null otherwise). |
| `queue_position` | integer | **Only for `not_started` status.** Position in the processing queue (1 = next to be processed). |
| `estimated_start_seconds` | integer | **Only for `not_started` status.** Estimated seconds until processing begins (based on ~30s per task). |

---

### GET `/api/download/<task_id>`

Download the generated audio file for a completed task.

**URL Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | string | The UUID of the task to download. |

**Success Response (200 OK):**
- **Content-Type:** `audio/wav`
- **Content-Disposition:** `attachment; filename="tts_<task_id>.wav"`
- **Body:** WAV audio file binary data

**Error Response (404 Not Found):**
```json
{
  "error": "File not found"
}
```
```json
{
  "error": "File missing on server"
}
```

---

### GET `/health`

Check the health status of the TTS service.

**Request:** No parameters required.

**Success Response (200 OK):**
```json
{
  "status": "healthy",
  "service": "tts-generator",
  "worker_running": true
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Health status (`"healthy"`). |
| `service` | string | Service name (`"tts-generator"`). |
| `worker_running` | boolean | Whether the background worker thread is active. |

---

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