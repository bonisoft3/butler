import os
import base64
from typing import Optional, Dict, Any
from google.adk.tools import ToolContext
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def transcribe_audio(tool_context: ToolContext, file_path: str, prompt: str = "Transcribe this audio file") -> Dict[str, Any]:
    """
    Transcribe an audio file using Google's Gemini model.
    
    Args:
        file_path (str): The absolute path to the audio file
        prompt (str): The transcription prompt (default: "Transcribe this audio file")
        
    Returns:
        dict: Transcription results
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": "Audio file not found",
                "file_path": file_path
            }
            
        # Check if file is an audio file
        _, ext = os.path.splitext(file_path)
        supported_formats = ['.mp3', '.wav', '.m4a', '.ogg', '.oga', '.opus', '.aac', '.flac']
        if ext.lower() not in supported_formats:
            return {
                "success": False,
                "error": f"File is not a supported audio format. Supported: {', '.join(supported_formats)}",
                "file_path": file_path,
                "extension": ext
            }
            
        # Read the audio file
        with open(file_path, 'rb') as audio_file:
            audio_data = audio_file.read()
            
        # Create the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Prepare the audio for the model
        mime_type_map = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.ogg': 'audio/ogg',
            '.oga': 'audio/ogg',
            '.opus': 'audio/opus',
            '.aac': 'audio/aac',
            '.flac': 'audio/flac'
        }
        
        audio_part = {
            "mime_type": mime_type_map.get(ext.lower(), 'audio/mpeg'),
            "data": audio_data
        }
        
        # Generate content
        response = model.generate_content([prompt, audio_part])
        
        return {
            "success": True,
            "file_path": file_path,
            "prompt": prompt,
            "transcription": response.text,
            "model": "gemini-2.0-flash"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error transcribing audio: {str(e)}",
            "file_path": file_path
        }

def analyze_audio_content(tool_context: ToolContext, file_path: str) -> Dict[str, Any]:
    """
    Analyze audio content including transcription and context understanding.
    
    Args:
        file_path (str): The absolute path to the audio file
        
    Returns:
        dict: Analysis results including transcription and content analysis
    """
    return transcribe_audio(
        tool_context,
        file_path, 
        "Transcribe this audio and provide a summary of the main topics discussed, tone, and any important information."
    )

def extract_speech_from_audio(tool_context: ToolContext, file_path: str) -> Dict[str, Any]:
    """
    Extract and transcribe speech from an audio file.
    
    Args:
        file_path (str): The absolute path to the audio file
        
    Returns:
        dict: Speech transcription results
    """
    return transcribe_audio(
        tool_context,
        file_path,
        "Transcribe all speech in this audio file. If multiple speakers, try to identify them. If no speech is detected, say 'No speech detected'."
    )