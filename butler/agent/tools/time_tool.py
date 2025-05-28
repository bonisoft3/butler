from datetime import datetime
from typing import Dict, Any

def get_current_time() -> Dict[str, Any]:
    """
    Get the current date and time.
    
    Returns:
        Dict[str, Any]: A dictionary containing:
            - status: "success" or "error"
            - error_message: Description of the error if status is "error"
            - result: Dictionary with current time information:
                - datetime: Full datetime string (YYYY-MM-DD HH:MM:SS)
                - date: Date string (YYYY-MM-DD)
                - time: Time string (HH:MM:SS)
                - hour: Current hour (0-23)
                - minute: Current minute (0-59)
                - day: Current day of month (1-31)
                - month: Current month (1-12)
                - year: Current year
                - weekday: Current day of week (0-6, where 0 is Monday)
    """
    try:
        now = datetime.now()
        return {
            "status": "success",
            "error_message": None,
            "result": {
                "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "hour": now.hour,
                "minute": now.minute,
                "day": now.day,
                "month": now.month,
                "year": now.year,
                "weekday": now.weekday()  # 0-6, where 0 is Monday
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error getting current time: {str(e)}",
            "result": None
        } 