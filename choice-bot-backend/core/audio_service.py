# file: core/audio_service.py

import whisper
from gtts import gTTS
import os
import time

# --- Configuration ---

# Ensure a directory exists for saving temporary audio files.
# In a high-scale production environment, use object storage like S3 instead.
AUDIO_OUTPUT_DIR = "static_audio"
os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True) # exist_ok=True: It prevents the function from raising an error if the directory already exists. If the directory is not there, it will be created. 
# If it already exists, the function does nothing, making the code robust and safe to run multiple times.

# Load Whisper model once. 'base' or 'small' model offers a good balance
# of speed and accuracy for real-time applications.
try:
    whisper_model = whisper.load_model("small") # This function is called from the whisper library the one from OpenAI to load one of its pre-trained speech recognition models.
    print("Whisper model loaded successfully.")
except Exception as e:
    print(f"Error loading Whisper model: {e}")
    whisper_model = None

# -- Speech -to-Text (STT) --

def transcribe_audio(audio_file_path: str) -> str:
    """
    Transcribes audio content from a file path using Whisper.

    Args:
        audio_file_path (str): Path to the saved audio file.

    Returns:
        str: The transcribed text.
    """
    if not whisper_model:
        return "[Error: Whisper model not loaded]"
    
    try:
        result = whisper_model.transcribe(audio_file_path, fp16=False) # fp16=False for CPU compatibility
        # fp16 stands for "half-precision floating-point format," which uses 16 bits to represent numbers. This format is primarily optimized for high-performance computing on GPUs, especially newer NVIDIA GPUs.
        # Setting fp16=False forces the model to use the standard 32-bit floating-point (FP32) format. This ensures compatibility with most CPUs and older GPUs, preventing potential hardware-related errors.
        return result["text"] # If transcription is successful, this line extracts the transcribed text, which is stored under the "text" key in the returned dictionary, and returns it.
    except Exception as e:
        print(f"Error during transcription: {e}")
        return f"[Transcription error: {e}]"
    
# -- Text-to-Speech (TTS) --

def generate_speech_audio(text: str, language:str) -> str:
    """
    Converts text to speech using Google TTS and saves it to a file.

    Args:
        text (str): The text content to convert.
        language (str): Language code (e.g., 'en', 'hi').

    Returns:
        str: The web-accessible path to the generated audio file.
    """
    try:
        tts = gTTS(text=text, lang=language, slow=False) # gTTS(): This function from the gTTS library is called to create a gTTS object. This object interfaces with Google's Text-to-Speech API.
        # slow=False: This parameter specifies the speaking speed. False sets it to a standard, non-slow speed.

        # Generate unique filename to avoid browser cahcing issue
        timestamp = int(time.time()* 1000) # It returns cureent time in seconds and we are multiplying by 1000 converts the time to milliseconds.
        filename = f"response_{language}_{timestamp}.mp3"
        file_path = os.path.join(AUDIO_OUTPUT_DIR, filename) # os.path.join(): This function from Python's os module intelligently and safely joins path components.
        # AUDIO_OUTPUT_DIR: The directory defined earlier (e.g., "static_audio").
        # os.path.join automatically uses the correct path separator for the operating system, ensuring the code works on Windows, Linux, or macOS.

        tts.save(file_path) # This method on the gTTS object saves the generated audio content to the specified file path.

        # Return the path accessible by the frontend client
        web_path = f"/{AUDIO_OUTPUT_DIR}/{filename}" # An f-string is used to create the web-accessible path for the audio file.
        # This path is what a web server would use to serve the file to a client-side application.
        return web_path
    except Exception as e:
        print(f"Error generating TTS audio: {e}")
        return ""