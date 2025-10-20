# file: core/audio_service.py

import whisper
from gtts import gTTS
import os

# New imports
import asyncio
from io import BytesIO
import io
import re
import subprocess

# Absolute path to ffmpeg (optional if PATH is set, but safer for Windows)
FFMPEG_PATH = r"C:\ffmpeg\bin\ffmpeg.exe"  # rely on PATH
# If you want to hardcode instead, set it like:
# FFMPEG_PATH = r"C:\tools\ffmpeg\bin\ffmpeg.exe"

# Set env variable so whisper/ffmpeg-python sees it
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG_PATH
os.environ["PATH"] = os.path.dirname(FFMPEG_PATH) + os.pathsep + os.environ["PATH"]

# For Debugg purposes
def check_ffmpeg():
    try:
        subprocess.run([FFMPEG_PATH, "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print("✅ ffmpeg found and ready.")
    except Exception as e:
        print(f"❌ ffmpeg not found: {e}")

check_ffmpeg()

# --- Configuration ---

# Ensure a directory exists for saving temporary audio files.
# In a high-scale production environment, use object storage like S3 instead.
#AUDIO_OUTPUT_DIR = "static_audio"
#os.makedirs(AUDIO_OUTPUT_DIR, exist_ok=True) # exist_ok=True: It prevents the function from raising an error if the directory already exists. If the directory is not there, it will be created. 
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

# Pre-processing the input audio with ffmpeg before transcription to increase the speech speed.
def preprocess_audio_for_stt(input_bytes: bytes, speed: float = 1.0) -> bytes:
    if speed == 1.0:
        return input_bytes
    process = subprocess.Popen(
        [FFMPEG_PATH, "-i", "pipe:0", "-filter:a", f"atempo={speed}", "-f", "wav", "pipe:1"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    output, error = process.communicate(input=input_bytes)
    return output if process.returncode == 0 else input_bytes

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

# New updates start here

LANGUAGE_MAP = {
    "en": "en",
    "english": "en",
    "en-US": "en",
    "en-GB": "en",
    "hi": "hi",
    "hindi": "hi"
    # extend as needed
}

def clean_text_for_tts(text: str) -> str:
    """Remove unwanted markdown/symbols from text before sending to TTS."""
    text = re.sub(r'[\*_`]', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # strip markdown links
    return text.strip()

def generate_gtts_bytes(text: str, language: str) -> bytes:
    """Generate MP3 bytes using gTTS (sync helper)."""
    try:
        lang_code = LANGUAGE_MAP.get(language.lower(), "en") if isinstance(language, str) else "en"
        cleaned_text = clean_text_for_tts(text)
        tts = gTTS(text=cleaned_text, lang=lang_code, slow=False)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        return buf.getvalue()
    except Exception as e:
        print(f"Error in TTS sync generation: {e}")
        return b""

def speed_up_audio_bytes(audio_bytes: bytes, speed: float = 1.2) -> bytes:
    try:
        process = subprocess.Popen(
            [FFMPEG_PATH, "-i", "pipe:0", "-filter:a", f"atempo={speed}", "-f", "mp3", "pipe:1"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        output, error = process.communicate(input=audio_bytes)
        if process.returncode != 0:
            print(f"ffmpeg error: {error.decode()}")
            return audio_bytes
        return output
    except Exception as e:
        print(f"Error speeding up audio: {e}")
        return audio_bytes

    
async def generate_speech_audio(text: str, language: str, speed: float = 1.2) -> bytes:
    """
    Generate TTS audio and return raw MP3 bytes, with optional speed adjustment.
    """
    audio_bytes = await asyncio.to_thread(generate_gtts_bytes, text, language)

    if not audio_bytes:
        return b""

    # Apply speed-up if needed (speed > 1.0)
    if speed and speed != 1.0:
        return await asyncio.to_thread(speed_up_audio_bytes, audio_bytes, speed)

    return audio_bytes
    

# New updates end here