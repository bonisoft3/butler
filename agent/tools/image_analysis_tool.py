import os
import base64
from typing import Optional, Dict, Any
from google.adk.tools import ToolContext
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def analyze_image(tool_context: ToolContext, file_path: str, prompt: str = "Describe this image in detail") -> Dict[str, Any]:
    """
    Analyze an image file using Google's Gemini Vision model.
    
    Args:
        file_path (str): The absolute path to the image file
        prompt (str): The analysis prompt (default: "Describe this image in detail")
        
    Returns:
        dict: Analysis results including description and any detected elements
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": "Image file not found",
                "file_path": file_path
            }
            
        # Check if file is an image
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
            return {
                "success": False,
                "error": "File is not a supported image format",
                "file_path": file_path,
                "extension": ext
            }
            
        # Read and encode the image
        with open(file_path, 'rb') as image_file:
            image_data = image_file.read()
            
        # Create the model
        model = genai.GenerativeModel('gemini-2.0-flash')
        
        # Prepare the image for the model
        image_part = {
            "mime_type": f"image/{ext[1:].lower()}" if ext[1:].lower() != 'jpg' else "image/jpeg",
            "data": image_data
        }
        
        # Generate content
        response = model.generate_content([prompt, image_part])
        
        return {
            "success": True,
            "file_path": file_path,
            "prompt": prompt,
            "analysis": response.text,
            "model": "gemini-2.0-flash"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Error analyzing image: {str(e)}",
            "file_path": file_path
        }

def extract_text_from_image(tool_context: ToolContext, file_path: str) -> Dict[str, Any]:
    """
    Extract text from an image using OCR capabilities of Gemini Vision.
    
    Args:
        file_path (str): The absolute path to the image file
        
    Returns:
        dict: Extracted text and OCR results
    """
    return analyze_image(
        tool_context,
        file_path, 
        "Extract all text visible in this image. If no text is found, say 'No text detected'."
    )

def identify_objects_in_image(tool_context: ToolContext, file_path: str) -> Dict[str, Any]:
    """
    Identify and list objects, people, or elements in an image.
    
    Args:
        file_path (str): The absolute path to the image file
        
    Returns:
        dict: List of identified objects and elements
    """
    return analyze_image(
        tool_context,
        file_path,
        "List and describe all objects, people, animals, or notable elements you can identify in this image. Be specific and detailed."
    )