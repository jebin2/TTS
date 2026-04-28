# TTS - Text-to-Speech

A modular FastAPI-based Text-to-Speech service with a vibrant Sketchbook aesthetic.

## Features
- Direct text input via web interface
- File upload support (.txt, .md)
- Multi-engine TTS (Chaterbox/Kitten/Kokoro)
- SQLite database for task queue management
- Sketchbook UI with hand-drawn elements and organic animations
- Real-time status and progress tracking

## Usage
Access the web interface at the hosted URL.

## API Endpoints
- `POST /api/tasks/upload` - Create a new TTS task (text or file)
- `GET /api/tasks` - List all tasks
- `GET /api/tasks/<id>` - Get specific task details
- `GET /api/download/<id>` - Download generated audio
- `GET /health` - Service health status

## Supported Inputs
Direct text input or `.txt`, `.md` files.
