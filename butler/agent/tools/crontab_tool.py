# agent/crontab_tool.py
from crontab import CronTab
import shlex # For escaping shell arguments
import json # Still needed for schedule_task
import os
import logging
from urllib.parse import urlparse
from typing import Optional, Dict, Any, List
from google.adk.tools import ToolContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get webhook URL from environment variable with fallback
WEBHOOK_URL = os.getenv("WHATSAPP_WEBHOOK_URL", "http://localhost:80/webhook")
COMMENT_PREFIX = "AGENT_SCHEDULED_MSG:"
QUERY_PREFIX = os.getenv("QUERY_PREFIX", "/query ")

def validate_webhook_url(url: str) -> bool:
    """Validate the webhook URL format.

    Args:
        url (str): The URL to validate

    Returns:
        bool: True if the URL is valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def schedule_task(cron_expression: str, message: str, tool_context: ToolContext) -> Dict[str, Any]:
    """Schedule a new task in the user's crontab.

    Args:
        cron_expression (str): A valid cron expression (e.g., "0 0 * * *" for daily at midnight)
        message (str): The message to be sent when the task executes
        user_id (str): The ID of the user who scheduled the task

    Returns:
        Dict[str, Any]: A dictionary containing:
            - status: "success" or "error"
            - error_message: Description of the error if status is "error"
            - result: True if task was scheduled successfully, False otherwise
    """
    if not validate_webhook_url(WEBHOOK_URL):
        error_msg = f"Invalid webhook URL: {WEBHOOK_URL}"
        logger.error(error_msg)
        return {
            "status": "error",
            "error_message": error_msg,
            "result": False
        }

    if not message or len(message) > 1000:  # Reasonable message length limit
        error_msg = "Message is empty or too long (max 1000 characters)"
        logger.error(error_msg)
        return {
            "status": "error",
            "error_message": error_msg,
            "result": False
        }

    try:
        user_id = tool_context.state.get("user_id", "")
        if not user_id:
            error_msg = "User ID not found in tool context"
            logger.error(error_msg)
            return {
                "status": "error",
                "error_message": error_msg,
                "result": False
            }
        # Create the JSON payload with the new structure
        json_payload = json.dumps({
            "name": "My past self",
            "from": user_id,
            "message": f"{QUERY_PREFIX}{message}"
        })

        # Construct the curl command
        command = f"curl -X POST -H {shlex.quote('Content-Type: application/json')} -d {shlex.quote(json_payload)} {shlex.quote(WEBHOOK_URL)}"

        cron = CronTab(user=True)
        job = cron.new(command=command, comment=f"{COMMENT_PREFIX}{message}")
        job.setall(cron_expression)
        
        if not job.is_valid():
            error_msg = f"Invalid cron expression: {cron_expression}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error_message": error_msg,
                "result": False
            }
            
        cron.write()
        logger.info(f"Scheduled: '{message}' with schedule: '{cron_expression}'")
        return {
            "status": "success",
            "error_message": None,
            "result": True
        }
    except FileNotFoundError:
        error_msg = "Crontab command not found. Is cron installed and in PATH?"
        logger.error(error_msg)
        return {
            "status": "error",
            "error_message": error_msg,
            "result": False
        }
    except Exception as e:
        error_msg = f"Error scheduling task: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "error_message": error_msg,
            "result": False
        }

def remove_task(message_identifier: str) -> Dict[str, Any]:
    """Remove a scheduled task from the user's crontab.

    Args:
        message_identifier (str): The message text that identifies the task to remove.
                                 This should match the message used when scheduling.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - status: "success" or "error"
            - error_message: Description of the error if status is "error"
            - result: True if task was removed, False if not found or error occurred
    """
    if not message_identifier:
        error_msg = "Message identifier cannot be empty"
        logger.error(error_msg)
        return {
            "status": "error",
            "error_message": error_msg,
            "result": False
        }

    try:
        cron = CronTab(user=True)
        removed_count = 0
        for job in list(cron): 
            if job.comment == f"{COMMENT_PREFIX}{message_identifier}":
                cron.remove(job)
                removed_count += 1
        
        if removed_count > 0:
            cron.write()
            logger.info(f"Successfully removed {removed_count} task(s) matching: '{message_identifier}'")
            return {
                "status": "success",
                "error_message": None,
                "result": True
            }
        else:
            msg = f"No scheduled task found with message: '{message_identifier}'"
            logger.info(msg)
            return {
                "status": "success",
                "error_message": None,
                "result": False
            }
    except FileNotFoundError:
        error_msg = "Crontab command not found. Is cron installed and in PATH?"
        logger.error(error_msg)
        return {
            "status": "error",
            "error_message": error_msg,
            "result": False
        }
    except Exception as e:
        error_msg = f"Error removing task: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "error_message": error_msg,
            "result": False
        }

def list_tasks() -> Dict[str, Any]:
    """List all tasks scheduled by this agent in the user's crontab.

    Returns:
        Dict[str, Any]: A dictionary containing:
            - status: "success" or "error"
            - error_message: Description of the error if status is "error"
            - result: List of task information strings if successful, empty list if no tasks found
    """
    try:
        cron = CronTab(user=True)
        scheduled_tasks = []
        task_number = 1
        
        for job in cron:
            if job.comment.startswith(COMMENT_PREFIX):
                message = job.comment[len(COMMENT_PREFIX):]
                cron_expression = job.slices.render()
                try:
                    try:
                        description = job.description(use_24hour_time_format=True, verbose=True)
                    except AttributeError:
                        description = job.description(use_24hour_time_format=True)
                    except Exception:
                        description = "N/A (could not generate description)"
                except Exception as e:
                    description = f"N/A (error: {str(e)})"

                task_info = f"{task_number}. Message: '{message}', Schedule: '{cron_expression}', When: '{description}'"
                scheduled_tasks.append(task_info)
                task_number += 1
        
        if not scheduled_tasks:
            logger.info("No tasks scheduled by this agent.")
            return {
                "status": "success",
                "error_message": None,
                "result": []
            }
        else:
            logger.info("Scheduled tasks:")
            for task_str in scheduled_tasks:
                logger.info(task_str)
            return {
                "status": "success",
                "error_message": None,
                "result": scheduled_tasks
            }

    except FileNotFoundError:
        error_msg = "Crontab command not found. Is cron installed and in PATH?"
        logger.error(error_msg)
        return {
            "status": "error",
            "error_message": error_msg,
            "result": []
        }
    except Exception as e:
        error_msg = f"Error listing tasks: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "error_message": error_msg,
            "result": []
        }

if __name__ == '__main__':
    # For testing purposes
    logger.info(f"Webhook URL: {WEBHOOK_URL}")
    
    # Example usage (uncomment to test, be careful with your crontab)
    if validate_webhook_url(WEBHOOK_URL):
        test_cron_expr = "*/1 * * * *" # Every minute for testing
        test_message = "Test task for listing"
        
        logger.info("\n--- Testing schedule_task ---")
        schedule_result = schedule_task(test_cron_expr, test_message, "test_user")
        if schedule_result["status"] == "success" and schedule_result["result"]:
            logger.info(f"Scheduled: '{test_message}'")
            
            logger.info("\n--- Testing list_tasks (after schedule) ---")
            list_result = list_tasks()
            if list_result["status"] == "success":
                for task in list_result["result"]:
                    logger.info(task)
            
            logger.info("\n--- Testing remove_task ---")
            remove_result = remove_task(test_message)
            if remove_result["status"] == "success" and remove_result["result"]:
                logger.info(f"Removed: '{test_message}'")
            else:
                logger.info(f"Could not remove or find task: '{test_message}'")
            
            logger.info("\n--- Testing list_tasks (after remove) ---")
            list_result = list_tasks()
            if list_result["status"] == "success":
                for task in list_result["result"]:
                    logger.info(task)
            
        else:
            logger.error(f"Failed to schedule test task: '{test_message}'")
            if schedule_result["error_message"]:
                logger.error(f"Error: {schedule_result['error_message']}")
            logger.info("\n--- Testing list_tasks (if schedule failed but to see existing) ---")
            list_result = list_tasks()
            if list_result["status"] == "success":
                for task in list_result["result"]:
                    logger.info(task)
    else:
        logger.error("\nSkipping crontab interaction tests because WEBHOOK_URL is invalid.")
        logger.info("\n--- Listing existing tasks (even if WEBHOOK_URL is invalid) ---")
        list_result = list_tasks()
        if list_result["status"] == "success":
            for task in list_result["result"]:
                logger.info(task)