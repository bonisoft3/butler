import asyncio
from google.adk import Agent
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from google.adk.events import Event, EventActions
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseConnectionParams
from typing import Optional
import time
import os
import logging
from tools.crontab_tool import schedule_task, remove_task, list_tasks
from tools.time_tool import get_current_time
from tools.file_tool import check_file_exists, get_file_info
from tools.image_analysis_tool import analyze_image, extract_text_from_image, identify_objects_in_image
from tools.audio_analysis_tool import transcribe_audio, analyze_audio_content, extract_speech_from_audio

session_service = InMemorySessionService()

APP_NAME = "WhatsAppWatchdog"

load_dotenv()

def load_agent_prompt():
    """Load the agent prompt from the prompts directory."""
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "prompt.md")
    try:
        with open(prompt_path, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        logging.error(f"Prompt file not found at {prompt_path}")
        raise

# Set up the model
AGENT_MODEL = os.getenv("AGENT_MODEL", "gemini-2.0-flash")


async def initialize_agent_and_runner():
    """
    Initializes the agent (with MCP tools) and the runner.
    Returns: (runner, agent, exit_stack)
    """
    mcp_url = os.getenv("WHATSAPP_MCP_URL", "http://whatsapp-mcp:3001/mcp")

    tools = [
        MCPToolset(
            connection_params=SseConnectionParams(url=mcp_url)
        ),
        schedule_task,
        remove_task,
        list_tasks,
        get_current_time,
        check_file_exists,
        get_file_info,
        analyze_image,
        extract_text_from_image,
        identify_objects_in_image,
        transcribe_audio,
        analyze_audio_content,
        extract_speech_from_audio
    ]   

    agent = Agent(
        model=AGENT_MODEL,
        name=APP_NAME,
        description="WhatsApp Butler, an intelligent assistant specializing in helping users find and understand information from their WhatsApp conversations.",
        instruction=load_agent_prompt(),
        tools=tools,
        output_key="final_response_text",
    )
    runner = Runner(
        agent=agent,
        app_name=APP_NAME,
        session_service=session_service
    )
    print(f"Loaded {len(tools)} tools from WhatsApp MCP server at {mcp_url}.")
    return runner, agent


async def call_agent_async(query: str, runner, user_id, session_id, media_info: Optional[dict] = None) -> str:
    """Sends a query to the agent and prints the final response."""
    print(f"\n>>> User Query: {query}")
    if media_info:
        print(f">>> Media Info: {media_info}")
    
    # Ensure session exists
    session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if session is None:
        session = await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        logging.info(f"  [Session] Created new session for user {user_id} with session ID {session_id}.")
    
    # If this is just for context storage, store media info and return
    if query.startswith("[MEDIA_CONTEXT_ONLY]") and media_info:
        logging.info(">>> Storing media context only, not running agent")
        
        # Store media info in session
        state_changes = {
            "user_id": user_id,
            "last_media_info": media_info,
            "last_media_timestamp": time.time()
        }
        actions_with_update = EventActions(state_delta=state_changes)
        system_event = Event(
            invocation_id="media_context_store",
            author="system",
            actions=actions_with_update,
            timestamp=time.time()
        )
        await session_service.append_event(session, system_event)
        logging.info(f">>> Media context stored: {media_info.get('filename', 'unknown')}")
        return ""

    # Prepare state changes including media context
    state_changes = {"user_id": user_id}
    
    # Store media information in session state for consecutive message processing
    if media_info:
        state_changes["last_media_info"] = media_info
        state_changes["last_media_timestamp"] = time.time()
    
    actions_with_update = EventActions(state_delta=state_changes)
    system_event = Event(
    invocation_id="media_context_update" if media_info else "user_id_update",
    author="system",
    actions=actions_with_update,
    timestamp=time.time()
    )
    await session_service.append_event(session, system_event)

    final_response_text = ""
    partial_response_text = ""
    
    # Enhance query with media information if available
    enhanced_query = query
    current_media = media_info
    
    # If no current media but there's a recent media in session, use it
    if not current_media:
        # Check recent events for media context
        events = session.events if hasattr(session, 'events') else []
        
        for event in reversed(events[-10:]):  # Check last 10 events
            if hasattr(event, 'actions') and event.actions and hasattr(event.actions, 'state_delta'):
                state_delta = event.actions.state_delta
                if state_delta and "last_media_info" in state_delta:
                    last_media = state_delta["last_media_info"]
                    last_timestamp = state_delta.get("last_media_timestamp", 0)
                    current_time = time.time()
                    
                    # Use last media if it was recent (within 5 minutes)
                    if last_media and (current_time - last_timestamp) < 300:
                        current_media = last_media
                        enhanced_query += f"\n\n[CONTEXT: Referencing recent media from previous message]"
                        break
    
    if current_media:
        file_path = current_media.get('filePath', '')
        file_exists = os.path.exists(file_path) if file_path else False
        mimetype = current_media.get('mimetype', 'unknown')
        filename = current_media.get('filename', 'unknown')
        
        enhanced_query += f"\n\nMedia Context:"
        enhanced_query += f"\n- File: {filename}"
        enhanced_query += f"\n- Type: {mimetype}"
        enhanced_query += f"\n- Path: {file_path}"
        enhanced_query += f"\n- Size: {current_media.get('filesize', 0)} bytes"
        enhanced_query += f"\n- Available: {file_exists}"
        
        if file_exists:
            if mimetype.startswith('audio/'):
                enhanced_query += f"\n\nAudio file ready for processing. Use transcribe_audio, analyze_audio_content, or extract_speech_from_audio with path: {file_path}"
            elif mimetype.startswith('image/'):
                enhanced_query += f"\n\nImage file ready for processing. Use analyze_image, extract_text_from_image, or identify_objects_in_image with path: {file_path}"
        else:
            enhanced_query += f"\n\nWarning: Media file not accessible at specified path."
    
    content = types.Content(role='user', parts=[types.Part(text=enhanced_query)])
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        # You can uncomment the line below to see *all* events during execution
        print(f"  [Event] Author: {event.author}, Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}")
        if event.partial and event.content and event.content.parts and event.content.parts[0].text:
            partial_response_text += event.content.parts[0].text
            logging.info(f"  [Partial] {partial_response_text}")

        # Key Concept: is_final_response() marks the concluding message for the turn.
        if event.is_final_response():
            if event.content and event.content.parts:
                # Assuming text response in the first part
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate: # Handle potential errors/escalations
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            # Add more checks here if needed (e.g., specific error codes)
            break # Stop processing events once the final response is found
    logging.info(f"Final response text: {final_response_text}")
    return final_response_text
