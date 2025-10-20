# file: app/main.py

import uvicorn # uvicorn: This is the high-performance ASGI (Asynchronous Server Gateway Interface) web server used to run FastAPI applications.
import os
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any
from dotenv import load_dotenv
import sys

# New imports while testing
import asyncio
import base64

# --- Load Environment Variables ---
# Call load_dotenv() before accessing any environment variables.
# This reads variables from the .env file and loads them into os.environ.
load_dotenv()

# Import core logic modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core import rag_service, audio_service, vector_store

# -- Application Intialization --
app = FastAPI(title="Voice Bot API", version="1.0.0")

# -- CORS Configuration --

# CORS (Cross-Origin Resource Sharing) is a browser-implemented security feature that allows web servers to control which origins (domains, protocols, or ports) can access their resources through HTTP headers, thereby enabling controlled, secure access to resources across different domains. 
# It extends the Same-Origin Policy (SOP) by allowing servers to opt into allowing cross-origin requests, which is crucial for modern web applications that rely on resources from third-party APIs and services. 

# Allow all origins for development purposes. Restrict this in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Example: ["http://localhost:3000"] for production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# -- Static File Serving --
# Mount the directory containing generated audio files to be served statically.
app.mount("/static_audio", StaticFiles(directory="static_audio"), name="static_audio")
# This line of code sets up a server route that makes the contents of the local static_audio directory available to web clients (like a user's browser) at the URL path /static_audio.
# For example, if you have a file named my_sound.mp3 inside the static_audio directory, a user can access it in their browser by going to the URL your-domain.com/static_audio/my_sound.mp3. This is how a web application provides assets like images, CSS, JavaScript, and, in this case, generated audio files, to the client-side of the application. 

# --- In-Memory Session Management ---
# Stores session data per connection. For production, replace with Redis or similar.
# Structure: { websocket_instance: {"user_name": str, "language": str, "chat_history": list, "rag_chain": Runnable} }
active_sessions: Dict[WebSocket, Dict[str, Any]] = {}

def detect_user_name(text:str) -> str | None: # -> str | None: This indicates the type of the value that the function is expected to return. 'None' suggest that the return value could be None.
    """Detects and extracts user name from introductory messages."""
    # Regex pattern to capture name: "My name is [Name]" or "I am [Name]"
    patterns = [
        r"my name is\s+([a-zA-Z]+)", # r means it is a raw string. Prefixing a string with r prevents backslashes from being interpreted as escape sequences. \s is a special sequence that matches any single whitespace character. It includes standard space ( ), tabs (\t), newlines (\n), and other forms of whitespace.
        r"i am\s+([a-zA-Z]+)",
        r"i'm\s+([a-zA-Z]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).capitalize() # match.group(1) returns only the text captured by the first set of parentheses (e.g., "John" in "My name is John"). If we give (0), then it will catch the whole string.
        return None

# It is used for saving contact info
# small rule-based intent detector (put above websocket handler)
def detect_intent(text: str) -> str | None:
    t = (text or "").lower()
    if any(kw in t for kw in ["book", "site visit", "site-visit", "schedule visit", "site visit", "visit site", "site visit"]):
        return "book_visit"
    if any(kw in t for kw in ["save my number", "my number is", "my phone is", "contact", "call me"]):
        return "save_contact"
    return None


# -- API Endpoints --

@app.post("/ingest/") # The decorator @app.post("/ingest/") is a syntax used in Python web frameworks, such as Flask or FastAPI, to associate a function with a specific HTTP endpoint. It tells the application to run the decorated function whenever it receives a POST request at the /ingest/ URL path.
async def http_ingest_data(client_id: str =Form(...), source_path:str = Form(...)): # async - allows the function to be paused and resumed, enabling it to perform I/O-bound tasks (like waiting for network or disk operations) without blocking the entire program. 
    # Form(...) - It tells the framework to expect a form field named "client_id" in the incoming request. The ... (Ellipsis) is a special object that indicates the field is required.
    """HTTP endpoint to trigger data ingestion for a specific client.
    In production, secure this endpoint (e.g., require admin auth token).
    """
    # Basic security check (example)
    # if not request.headers.get("Authorization") == "Bearer ADMIN_SECRET_KEY":
    #     raise HTTPException(status_code=401, detail="Unauthorized")

    if not os.path.isdir(source_path):
        raise HTTPException(status_code=400, detail=f"Source directory not found: {source_path}") # f-strings - It stands for formatted string literal, more commonly known as an "f-string". The f prefix tells Python to look for expressions enclosed in curly braces {} within the string. 
    
    success = vector_store.load_and_embed_documents(client_id,source_path)
    if success:
        return {"message" : f"Ingestion successful for client '{client_id}'."}
    else:
        raise HTTPException(status_code=500, detail="Ingestion failed.")
    
# -- WebSocket Chat Endpoint --

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()

    # 1. Initialize session state and RAG chain
    try:
        rag_chain = rag_service.create_rag_chain(client_id)
        session_data = {
            "user_name": None,
            "language": "en",
            "chat_history": [],
            "rag_chain": rag_chain
        }
        active_sessions[websocket] = session_data
        print(f"WebSocket connection established for client : {client_id}")
    except ValueError as e:
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close(code=1008)
        return

    # 2. Send initial greeting (handle bytes or path)
    initial_greeting = "Hello! My name is VOICE, how can I assist you today?"
    try:
        tts_result = await audio_service.generate_speech_audio(initial_greeting, session_data["language"])
        # If bytes -> base64; if string -> treat as url/path
        if isinstance(tts_result, (bytes, bytearray)):
            greeting_audio_base64 = base64.b64encode(bytes(tts_result)).decode("utf-8")
            greeting_audio_url = None
        elif isinstance(tts_result, str) and tts_result:
            # tts_result may be either a returned URL like "/static/audio/xxx.mp3" or a file path
            greeting_audio_base64 = ""
            # if starts with '/', it's probably a URL path; otherwise treat as path
            if tts_result.startswith("/"):
                greeting_audio_url = f"http://localhost:8000{tts_result}"  # frontend-friendly absolute url
            else:
                greeting_audio_url = f"http://localhost:8000/static/audio/{os.path.basename(tts_result)}"
        else:
            greeting_audio_base64 = ""
            greeting_audio_url = None
    except Exception as e:
        print(f"TTS generation failed for greeting: {e}")
        greeting_audio_base64 = ""
        greeting_audio_url = None

    await websocket.send_json({
        "type": "response",
        "sender": "bot",
        "text": initial_greeting,
        "audio_base64": greeting_audio_base64,
        "audio_url": greeting_audio_url
    })

    # 3. Main loop - handle incoming messages
    try:
        while True:
            data = await websocket.receive_json()
            print(f"--- RECEIVED DATA: {data} ---")

            # Language switch
            if data.get("type") == "language_switch":
                session_data['language'] = data["language"]
                print(f"Switched language to: {session_data['language']}")
                await websocket.send_json({"type": "status", "message": f"Language set to {data['language']}"})
                continue

            # Determine query_text
            query_text = None
            if data.get("type") == "text_query":
                query_text = data.get("text", "").strip()
                # echo user's text handled in frontend earlier if needed
            elif data.get("type") == "audio_query":
                import base64 as _b64
                audio_data = _b64.b64decode(data["audio_data"])
                temp_audio_path = f"temp_audio_{id(websocket)}.wav"
                with open(temp_audio_path, "wb") as f:
                    f.write(audio_data)

                # Run Whisper transcription in a thread
                try:
                    query_text = await asyncio.to_thread(audio_service.transcribe_audio, temp_audio_path)
                finally:
                    # Cleanup only after transcription completes
                    try:
                        os.remove(temp_audio_path)
                    except Exception:
                        pass
                # ✅ Echo user’s transcribed message back to frontend chat
                await websocket.send_json({
                    "type": "user_message",
                    "sender": "user",
                    "text": query_text
                 })
            else:
                await websocket.send_json({"type": "error", "message": "Unsupported message type."})
                continue

            # Personalization
            if not session_data["user_name"]:
                user_name = detect_user_name(query_text)
                if user_name:
                    session_data["user_name"] = user_name
                    print(f"Captured user name: {user_name}")
                    
            # RAG processing
            try:
                response_text = await rag_service.process_query(
                    query=query_text,
                    session_data=session_data,
                    client_id=client_id,
                    rag_chain=session_data["rag_chain"]
                )
            except Exception as e:
                print(f"Error during RAG processing: {e}")
                response_text = "Sorry — I had an error processing your request."

            # Generate TTS (robust handling for bytes or returned path)
            try:
                #cleaned_response = clean_text_for_tts(response_text)
                tts_result = await audio_service.generate_speech_audio(response_text, session_data["language"])

                if isinstance(tts_result, (bytes, bytearray)):
                    response_audio_base64 = base64.b64encode(bytes(tts_result)).decode("utf-8")
                    response_audio_url = None
                elif isinstance(tts_result, str) and tts_result:
                    # backend returned a path/URL string
                    response_audio_base64 = ""
                    if tts_result.startswith("/"):
                        response_audio_url = f"http://localhost:8000{tts_result}"
                    else:
                        response_audio_url = f"http://localhost:8000/static/audio/{os.path.basename(tts_result)}"
                else:
                    response_audio_base64 = ""
                    response_audio_url = None

            except Exception as e:
                print(f"TTS generation failed: {e}")
                response_audio_base64 = ""
                response_audio_url = None

            # Send response (both keys included for compatibility)
            await websocket.send_json({
                "type": "response",
                "sender": "bot",
                "text": response_text,
                "audio_base64": response_audio_base64,
                "audio_url": response_audio_url
            })

            # Update chat history
            session_data["chat_history"].append(("user", query_text))
            session_data["chat_history"].append(("assistant", response_text))
            session_data["chat_history"] = session_data["chat_history"][-10:]

    except WebSocketDisconnect:
        print(f"WebSocket connection closed for client: {client_id}")
    except Exception as e:
        print(f"An error occurred in WebSocket connection: {e}")
    finally:
        if websocket in active_sessions:
            del active_sessions[websocket]


# --- Run Application ---
if __name__ == "__main__":
    # Example: how to run data ingestion before starting server.
    # Replace 'client_demo' with actual client ID and './data/client_demo' with GDrive path.
    print("Running initial data ingestion for demo client...")
    vector_store.load_and_embed_documents(client_id="client_demo", source_directory="./data/client_demo")
    print("Starting FastAPI server...")
    uvicorn.run(app, host="0.0.0.0", port=8000) # host="0.0.0.0": This argument configures the server to listen on all available network interfaces, making it accessible not just from the local machine (127.0.0.1), but also from other computers on the same network.



                


