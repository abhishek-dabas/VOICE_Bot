# VOICE_Bot

# VOICE — RAG Voice Assistant (Voice Bot)

[![Status](https://img.shields.io/badge/status-beta-yellow)](https://github.com/)
[![Language](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## Project overview

**VOICE** is a real-time voice + text assistant built with a Retrieval-Augmented Generation (RAG) pipeline.  
It ingests client documents, stores them in a vector store (ChromaDB), and answers user queries using a combination of a vector retriever and a large language model (Google Gemini in the original prototype). The assistant accepts input as text or audio (microphone), and returns answers both as text and synthesized speech (TTS).

This repository contains the backend (FastAPI) and the core RAG/TTS/STT services that power the voice assistant.

---

## Key features

- Ingests documents (.pdf, .docx, .txt, .csv) into a ChromaDB collection per client.
- Real-time frontend communication using WebSocket (`/ws/{client_id}`).
- Speech-to-text (STT) via Whisper (local model).
- Retrieval from ChromaDB + LLM generation (Gemini via `genai`).
- Text-to-speech (TTS) using gTTS; audio speed adjusted via `ffmpeg`.
- Returns both `text` and `audio_url` to the frontend for playback.
- Safe session handling and in-memory session map (`active_sessions`) for demo usage.

---

## Tech stack

- Python 3.11 / 3.12 (recommended)
- FastAPI + Uvicorn (ASGI)
- Whisper (speech-to-text)
- gTTS (text-to-speech)
- ChromaDB (vector store) via LangChain integration
- Google Gemini API (via `google.generativeai`) for LLM responses (can be replaced with other LLMs)
- `ffmpeg` (for audio speed / audio processing)
- WebSocket for real-time chat

---

## Repository structure (important files)

.
├─ app/
│ ├─ main.py # FastAPI + WebSocket entrypoint
├─ core/
│ ├─ rag_service.py # RAG chain, Gemini calls
│ ├─ vector_store.py # Ingest + retrieval (ChromaDB)
│ ├─ audio_service.py # STT (Whisper) + TTS (gTTS) + ffmpeg usage
├─ data/
│ ├─ client_demo/ # sample documents for ingestion
├─ static_audio/ # generated audio files (served)
├─ chroma_db_store/ # ChromaDB persistence directory
├─ README.md
├─ requirements.txt
└─ .env.example

## Requirements & prerequisites

- Python 3.11 or 3.12 (recommended). Avoid Python 3.13 due to some third-party incompatibilities noted previously.
- `ffmpeg` installed and available on PATH, or set `FFMPEG_PATH` in the `audio_service.py`.
- Google Gemini API key (if using Gemini) — store as environment variable.
- Install required Python packages (see `requirements.txt` below).

### Example `requirements.txt` (trim/adjust to match installed versions)

fastapi
uvicorn
python-dotenv
whisper
gtts
langchain
langchain-google-genai
langchain-chroma
langchain-huggingface
chromadb
google-generativeai
pydub # optional if used (we moved to ffmpeg streams)

## Environment variables

Create a `.env` file (do **not** commit secrets). Example `.env`:

GOOGLE_API_KEY=YOUR_GOOGLE_API_KEY
OPENAI_API_KEY=OPTIONAL_IF_USED
CUDA_AVAILABLE= # set if you have CUDA (e.g., "1")


## Installation / Setup (local dev)

1. Clone the repo:
   git clone https://github.com/<your-username>/choice-bot.git
   cd choice-bot
Create & activate a virtual environment:

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate
Install dependencies:

pip install -r requirements.txt
Install ffmpeg on your machine and ensure ffmpeg is on PATH:

Windows: download a static build (e.g., gyan.dev/BtbN), extract, and add .../ffmpeg/bin to PATH.

Verify in a new terminal: ffmpeg -version

Create .env using .env.example and fill in keys:

cp .env.example .env
# edit .env
Add sample documents for demo ingestion:

Place .pdf, .docx, .txt files under data/client_demo/ (already included in this repo as examples).

Run ingestion (optional)
You can pre-ingest documents before starting the server (recommended for demo):

python -c "from core import vector_store; vector_store.load_and_embed_documents('client_demo','./data/client_demo')"
Or simply run the app which in __main__ may ingest automatically for demo client.


Run the backend

# from repo root, with venv activated
python app/main.py
# or run via uvicorn directly:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
The server exposes:

Static audio files: http://localhost:8000/static_audio/<filename>.mp3

WebSocket chat endpoint: ws://localhost:8000/ws/{client_id} (example: client_demo)

WebSocket message format
Client → Server


Text query:

{
  "type": "text_query",
  "text": "What is the full form of AI ?"
}
Audio query (base64-encoded audio data):

{
  "type": "audio_query",
  "audio_data": "<BASE64_AUDIO_BYTES>"
}
Language switch:

{
  "type": "language_switch",
  "language": "en"
}
Server → Client

Initial and subsequent responses:

{
  "type": "response",
  "sender": "bot",
  "text": "AI stands for Artificial Intelligence",
  "audio_url": "/static_audio/response_en_123456789.mp3"
}

Errors:
{
  "type": "error",
  "message": "Description of error"
}
Troubleshooting (common issues & fixes)
[Transcription error: [WinError 2] The system cannot find the file specified]

Means ffmpeg is not found. Install ffmpeg and ensure it is on PATH, or set FFMPEG_PATH in audio_service.py. Restart your shell/IDE after installing.

TypeError: Object of type coroutine is not JSON serializable

Happens when an async function returns a coroutine that wasn’t awaited. Make sure to await generate_speech_audio(...) and any other async functions before sending results via websocket.send_json().

No retrieved documents / poor answers

Increase k in get_vector_retriever(client_id, k=...) or tweak embedding model. Confirm ingestion succeeded and that the collection name is client_<client_id>.


Slow TTS

We use gTTS + ffmpeg atempo to increase playback speed in memory. For production, consider cloud TTS providers (AWS Polly, Google TTS) for higher quality and SSML support.


Scaling & production notes


Move static_audio/ to S3 (or any object storage) and return signed URLs; this allows horizontal scaling and offloads static serving.

Run ChromaDB in a managed or self-hosted service (Docker) — use persistent volumes.

Use a queue (Celery/RabbitMQ) for heavy tasks (ingestion, offline embedding).

Use Redis for session state instead of in-memory active_sessions for multi-process scaling.

Add timeouts and retries around the LLM calls (Gemini/OpenAI).

Contributing
PRs welcome — please open issues for bugs or feature requests. Keep secrets out of the repo.


License
MIT License — see LICENSE file.


Contact

Abhishek — abhishek050505@gmail.com

LinkedIn: https://www.linkedin.com/in/abhishekdabas/
