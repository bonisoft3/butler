import os
from typing import Optional, Dict, Any
from google.adk.tools import ToolContext

def check_file_exists(tool_context: ToolContext, file_path: str) -> Dict[str, Any]:
    """
    Check if a file exists and get basic information about it.
    
    Args:
        file_path (str): The absolute path to the file to check
        
    Returns:
        dict: Information about the file including existence, size, and type
    """
    try:
        if not file_path:
            return {
                "exists": False,
                "error": "No file path provided"
            }
            
        exists = os.path.exists(file_path)
        
        if not exists:
            return {
                "exists": False,
                "path": file_path,
                "error": "File not found"
            }
            
        # Get file stats
        stats = os.stat(file_path)
        
        # Get file extension
        _, ext = os.path.splitext(file_path)
        
        return {
            "exists": True,
            "path": file_path,
            "size": stats.st_size,
            "extension": ext.lower(),
            "is_image": ext.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'],
            "readable": os.access(file_path, os.R_OK)
        }
        
    except Exception as e:
        return {
            "exists": False,
            "path": file_path,
            "error": f"Error checking file: {str(e)}"
        }

def get_file_info(tool_context: ToolContext, file_path: str) -> Dict[str, Any]:
    """
    Get detailed information about a media file.
    
    Args:
        file_path (str): The absolute path to the file
        
    Returns:
        dict: Detailed file information
    """
    try:
        file_check = check_file_exists(file_path)
        
        if not file_check["exists"]:
            return file_check
            
        # Add more detailed info for images
        if file_check["is_image"]:
            try:
                # Try to get image dimensions (requires PIL if available)
                try:
                    from PIL import Image
                    with Image.open(file_path) as img:
                        file_check["image_width"] = img.width
                        file_check["image_height"] = img.height
                        file_check["image_mode"] = img.mode
                        file_check["image_format"] = img.format
                except ImportError:
                    file_check["note"] = "PIL not available for detailed image analysis"
                except Exception as img_error:
                    file_check["image_error"] = str(img_error)
            except Exception:
                pass
                
        return file_check
        
    except Exception as e:
        return {
            "exists": False,
            "path": file_path,
            "error": f"Error getting file info: {str(e)}"
        }