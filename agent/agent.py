import asyncio
from google.adk import Agent
from dotenv import load_dotenv
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from google.adk.events import Event, EventActions
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, SseServerParams
from typing import Optional
import time
import os
import logging
from tools.crontab_tool import schedule_task, remove_task, list_tasks
from tools.time_tool import get_current_time

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
            connection_params=SseServerParams(url=mcp_url)
        ),
        schedule_task,
        remove_task,
        list_tasks,
        get_current_time
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


async def call_agent_async(query: str, runner, user_id, session_id) -> str:
    """Sends a query to the agent and prints the final response."""
    print(f"\n>>> User Query: {query}")

    session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if session is None:
        # Create a new session if it doesn't exist
        session = await session_service.create_session(app_name = APP_NAME, user_id=user_id, session_id=session_id)
        logging.info(f"  [Session] Created new session for user {user_id} with session ID {session_id}.")

    state_changes = {"user_id": user_id}
    actions_with_update = EventActions(state_delta=state_changes)
    system_event = Event(
    invocation_id="user_id_update",
    author="system",
    actions=actions_with_update,
    timestamp=time.time()
    )
    await session_service.append_event(session, system_event)

    final_response_text = ""
    partial_response_text = ""
    content = types.Content(role='user', parts=[types.Part(text=query)])
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