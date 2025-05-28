from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import asyncio
import logging
from typing import Dict, Any
import os
from agent import call_agent_async, initialize_agent_and_runner
from contextlib import asynccontextmanager
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Get message prefix from environment variable or use default
QUERY_PREFIX = os.getenv("QUERY_PREFIX", "/query ")
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY")

@asynccontextmanager
async def lifespan(app: FastAPI):
    runner, agent  = await initialize_agent_and_runner()
    app.state.runner = runner
    app.state.agent = agent
    logger.info("Agent and runner initialized and stored in app.state.")
    yield
    logger.info("Agent and runner resources closed.")

app = FastAPI(title="WhatsApp Butler Webhook", lifespan=lifespan)

async def send_message_to_whatsapp(response: str, chat_id: str):
    """
    Send a message to WhatsApp
    Args:
        response (str): The message to send
        chat_id (str): The chat ID of the message
    """
    # Send the message to the WHATSAPP_API_URL
    async with httpx.AsyncClient() as client:
        await client.post(f"{WHATSAPP_API_URL}/send", 
                          headers={"Authorization": f"Bearer {WHATSAPP_API_KEY}"},
                          json={"message": response, "number": chat_id})
    logger.info(f"Message sent to WhatsApp: {response} to {chat_id}")

async def process_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process incoming WhatsApp message and call agent
    
    Args:
        message (Dict[str, Any]): The incoming message data
        
    Returns:
        Dict[str, Any]: Response containing status and agent response   
    """
    try:
        # Extract message content
        content = message.get("message", "")
        sender = message.get("name", "")
        chat_id = message.get("from", "")
        if not content:
            return JSONResponse(
                status_code=200,
                content={"status": "success"}
            )

        # Skip if the message is not from the bot
        if not content.startswith(QUERY_PREFIX):
            return JSONResponse(
                status_code=200,
                content={"status": "success"}
            )
            
        logger.info(f"Processing message from {sender} in chat {chat_id}")
        
        # Use runner from app.state
        runner = app.state.runner
        response = await call_agent_async(content, runner, chat_id, chat_id)
        logger.info(f"Agent response: {response}")
        await send_message_to_whatsapp(response, chat_id)
        return JSONResponse(
            status_code=200,
            content={"status": "success"}
        )
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhook")
async def webhook(request: Request):
    """
    Webhook endpoint for receiving WhatsApp messages
    
    Args:
        request (Request): The incoming request
        
    Returns:
        JSONResponse: Response containing status and agent response
    """
    try:
        data = await request.json()
        logger.info(f"Received webhook: {data}")
        await process_message(data)
        return JSONResponse(
            status_code=200,
            content={"status": "success"}
        )
    except Exception as e:
        logger.error(f"Webhook error: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    
    Returns:
        Dict[str, str]: Health status
    """
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment variable or use default
    port = int(os.getenv("WEBHOOK_PORT", "8000"))
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    ) 