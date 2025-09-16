# file: app/main.py

import uvicorn # uvicorn: This is the high-performance ASGI (Asynchronous Server Gateway Interface) web server used to run FastAPI applications.
import os
import re
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any
from dotenv import load_dotenv

# --- Load Environment Variables ---
# Call load_dotenv() before accessing any environment variables.
# This reads variables from the .env file and loads them into os.environ.
load_dotenv()

# Import core logic modules
from core.chat import rag_service, audio_service, vector_store

# -- Application Intialization --
app = FastAPI(title="Choice Bot API", version="1.0.0")

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

@app.websocket("/ws/{client_id}") # WebSockets provide a full-duplex/bidirectional communication channel over a single, long-lived connection, allowing for real-time data exchange between the client and server.
# The @app.websocket("/ws/{client_id}") decorator is used in web frameworks like FastAPI to define a WebSocket endpoint. It specifies that the function it decorates will handle WebSocket connections made to the URL path /ws/{client_id}, where {client_id} is a dynamic segment that can vary for each connection. 
# /ws/: The path prefix. A client would use this as part of the URL to initiate a WebSocket handshake with the server. wss for secured connection and ws for unsecured connection.
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time chat with RAG and TTS. It handles real-time chat interactions via WebSocket."""
    await websocket.accept() # It is the command that formally completes the WebSocket handshake and accepts the client's connection. 

    # 1. Initialize session state and RAG chain for the connecting client
    try:
        rag_chain = rag_service.create_rag_chain(client_id) # This line calls a function from a rag_service to build a new RAG chain for the specified client_id. The create_rag_chain method suggests that a new, dedicated chain is being generated for the new client.
        session_data = { # a Python dictionary named session_data
            "user_name": None, # It creates a key "user_name". It is set to None, indicating that the user has not yet provided or been identified by a name. The application will populate this value later
            "language": "en", # Default language
            "chat_history": [], # holds an empty list ([]) to store the ongoing conversation history for this session.As the user and the AI exchange messages, they will be appended to this list
            "rag_chain": rag_chain # rag_chain object that was just created. By placing the rag_chain instance in the session data, the application can easily access and reuse the same RAG system for the duration of the user's session. No need to recreate it for every message.
        }
        active_sessions[websocket] = session_data # active_sessions is a dictionary that maps each active WebSocket connection (websocket) to its corresponding session data (session_data). This allows the server to manage multiple user sessions simultaneously, each with its own state and context.
        print(f"WebSocket connection established for client : {client_id}")
    except ValueError as e:
        await websocket.send_json({"type": "error", "message":str(e)}) 
        await websocket.close(code=1008) # 1008 - Policy Violation
        return
    
    # 2. Send intial greeting message
    initial_greeting = "Hello! My name is CHOICE, how can I assist you today?"
    tts_path = audio_service.generate_speech_audio(initial_greeting, session_data["language"]) # tts_path receives function's return value which is likely a path where the generated audio file is stored.
    # It is generating a speech audio file from text and sending it, along with the original text, to a client via a WebSocket. audio_service is an object of TTS and converts text into spoken audio.
    await websocket.send_json({ # .send_json(...): This method sends data to the client, converting the dictionary into a JSON-formatted string before sending.
        "type": "response",
        "sender":"bot", # It indicates that the message originated from the bot or user.
        "text": initial_greeting,
        "audio_url": tts_path # It sends the URL or path to the audio file
    })

    # 3. Listen for incmoning messages (text or audio)
    try:
        while True:
            data = await websocket.receive_json() # .receive_json(): This method waits for a message from the client. When a message is received, it parses it and converts it into a Python dictionary or list.

            if data["type"] == "language_switch":
                session_data['language'] = data["language"]
                print(f"Switched language to: {session_data['language']}")
                await websocket.send_json({"type":" status", "message": f"Language set to {data['language']}"})
                continue

            # Process user query (text)
            if data["type"] == "text_query":
                query_text = data["text"]
            
            elif data["type"] == "audio_query":
                # Audio data received as base64 string from frontend. Why? Raw audio is binary data. It can't be sent directly inside a JSON message, which is text-based.
                import base64 # The frontend uses Base64 encoding to package the binary audio data into a safe text string. 
                audio_data =  base64.b64decode(data["audio_data"]) # base64.b64decode() function is the backend's way of "unpackaging" that text string and converting it back into the original raw audio data.
                # Save temprorary audio file for Whisper processing as Whisper AI model is designed to read audio from a file on the disk, not directly from memory. So, we must save the unpackaged audio data as a temporary file
                temp_audio_path =  f"temp_audio_{id(websocket)}.wav" #  Use a unique name for each WebSocket connection to avoid conflicts.
                with open(temp_audio_path,"wb") as f: # This opens the new file in "write binary" (wb) mode. This is crucial because audio is binary data, not plain text.
                    f.write(audio_data)
                
                query_text = audio_service.transcribe_audio(temp_audio_path) # passes the path of our new audio file to the Whisper service. Whisper "listens" to the file and returns the words it hears as a standard text string, which gets stored in the query_text variable.
                os.remove(temp_audio_path) # Clean up temp file

                # Send transcribed text back to client for confirmation/display
                await websocket.send_json({
                    "type": "user_message",
                    "sender": "user",
                    "text": query_text
                })

                # -- RAG Procession and State Update --
                # Check for name extraction
                if not session_data["user_name"]:
                    user_name = detect_user_name(query_text)
                if user_name:
                    session_data["user_name"] = user_name
                    print(f"Captured user name: {user_name}") 

                # Generate response using RAG chain
                response_text = rag_service.process_query( # It sends a user's text query and other session-specific data to a rag_service and stores the resulting text response in the response_text variable.
                query = query_text, # This provides the user's raw text input to the RAG system. The RAG chain will use this query to search its knowledge base for relevant documents.
                session_data = session_data, # This passes the current session's data. This can include conversation history, user preferences (like language), and other.
                client_id = client_id,
                rag_chain = session_data["rag_chain"] # This provides the specific RAG chain to be used for processing the query. A RAG chain is a predefined sequence of operations, which might involve steps like: 
                            # Preprocessing the query.
                            # Retrieving documents from a vector database based on the query.
                            # Augmenting the original user query with the retrieved documents.
                            # Sending the augmented query to an LLM for generation.
                )

                # Generate TTS for the response
                response_audio_url = audio_service.generate_speech_audio(
                    response_text,
                    session_data["language"]
                )

                # -- Send response back to client --
                await websocket.send_json({
                    "type": "response",
                    "sender": "bot",
                    "text": response_text,
                    "audio_url": response_audio_url
                })

                # Update Chat History (simple version)
                session_data["chat_history"].append(("user", query_text))
                session_data["chat_history"].append(("assistant", response_text))
                # Limit Chat History Length to save memory, manage token limits sent to LLMs, maintain relevance(as older messages may become less relevant over time) and reduce computational load(less amount of data to LLMs so reduces latency also).
                session_data["chat_history"] = session_data["chat_history"][-10:]  # Keep only last 10 exchanges
    
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
    # print("Running initial data ingestion for demo client...")
    # vector_store.load_and_embed_documents(client_id="client_demo", source_directory="./data/client_demo")
    print("Starting FastAPI server...")
    uvicorn.run(app, host="0.0.0.0", port=8000) # host="0.0.0.0": This argument configures the server to listen on all available network interfaces, making it accessible not just from the local machine (127.0.0.1), but also from other computers on the same network.



                


