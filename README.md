# WhatsApp Butler 🤖👔

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg?style=for-the-badge)](LICENSE)

Imagine having a personal WhatsApp assistant that understands your needs, finds what you're looking for, manages your conversations effortlessly, and even helps you schedule messages for the future. Meet WhatsApp Butler - your elegant AI companion that transforms how you interact with WhatsApp.

## How It Works

WhatsApp Butler seamlessly integrates with your WhatsApp account, bringing the power of AI directly to your conversations. Just like having a personal butler at your service, it's always ready to assist you. All responses from the butler will be delivered in your own personal chat with yourself, keeping your interactions private and organized:

```
You: /query Find John's message about the project deadline
Butler: I found this message from John (Yesterday, 3:45 PM):
        "Don't forget our project deadline is this Friday at 5pm. Please submit all files to the shared folder."
        
You: /query Schedule a reminder about the project deadline for Friday at 4pm
Butler: I've scheduled a reminder for Friday at 4:00 PM:
        "Reminder: Project deadline is at 5pm today. Please submit all files to the shared folder."
        
You: /query Summarize today's messages in the family group
Butler: Summary of today's messages in "Family Group":
        - Mom announced she's making lasagna for dinner tonight
        - Dad will be home late, around 8pm
        - Your sister shared photos from her trip to the beach
        - Everyone discussed weekend plans (consensus is movie night on Saturday)
        
You: /query Set up a daily reminder to check the family group at 8pm
Butler: I've set up a daily reminder for 8:00 PM:
        "Time to check the family group for any updates!"
        
You: /query What was the address of that restaurant Mark recommended?
Butler: Mark shared this address on Tuesday:
        "Let's try that new Italian place, Bella Cucina at 123 Main Street. They have amazing pasta!"
```

💡 **Tip:** For a cleaner experience, use the assistant in your personal chat with yourself. Since all responses are sent from your own account (not a separate "butler" contact), this keeps other conversations uncluttered and helps maintain context without confusing others.

WhatsApp Butler can help you:

- 📝 Generate smart summaries of conversations (perfect for catching up on busy group chats)
- 🔍 Find that elusive message with specific information (addresses, phone numbers, meeting details)
- 📤 Forward important messages with added context (save time explaining background information)
- 💬 Answer complex questions about your conversations (who said what and when)
- 🧠 Maintain context between requests (have natural, flowing interactions)
- ⏰ Schedule messages and reminders (set up one-time or recurring notifications)

### Technical Details

1. **WhatsApp Web Connection**  
   WhatsApp Butler connects to your WhatsApp account using the [whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js) library. On first setup, you'll need to scan a WhatsApp Web QR code to authenticate.

2. **Browser-like Behavior via MCP Server**  
   The system behaves like a browser running WhatsApp Web, powered by a fork of [wweb-mcp](https://github.com/pnizer/wweb-mcp) server, which manages the WhatsApp session and message operations.

3. **Command Detection**  
   Any message you send (in your personal chat with yourself) that starts with the prefix `/query` is automatically detected and forwarded to the AI agent.

4. **Agent Querying and Actions**  
   The agent uses the WhatsApp MCP Server to search your WhatsApp chat history, answer your queries, and can also send messages on your behalf if you request it. It can schedule messages for future delivery using the system's cron service.

5. **Private Answer Delivery**  
   All answers from the agent are sent back to your personal chat with yourself, ensuring privacy and keeping your other conversations uncluttered.



## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.9 or higher
- WhatsApp account
- Google API key for Gemini AI
- Sudo access (for setup script)

### Installation

1. Clone the repository with submodules:
```bash
git clone --recursive https://github.com/andrepaim/whatsapp-watchdog.git
cd whatsapp-watchdog
```

2. Create a `.env` file with required variables:
```bash
# WhatsApp API Configuration
WHATSAPP_API_KEY=your_whatsapp_api_key
QUERY_PREFIX=/query  # Optional: customize the command prefix
GOOGLE_API_KEY=your_google_api_key
GOOGLE_GENAI_USE_VERTEXAI=false  # Set to true if using Vertex AI
AGENT_MODEL=your_agent_model_name (e.g. gemini-2.0-flash)
```

3. Run the setup script:
```bash
chmod +x setup-whatsapp.sh
./setup-whatsapp.sh
```

4. Start the services:
```bash
make docker-compose-up
```

## Architecture

The system consists of three main services:

### WhatsApp API Service
- Handles WhatsApp Web authentication
- Manages message operations
- Provides REST API endpoints
- Maintains persistent session

### WhatsApp MCP Service 
- Provides Server-Sent Events (SSE)
- Handles real-time message streaming
- Connects to WhatsApp API service
- Processes message events

### Webhook Service 
- Processes incoming webhook requests
- Integrates with Google's Gemini AI
- Manages conversation context
- Generates AI responses

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| WHATSAPP_API_KEY | API key for WhatsApp services | Required |
| WHATSAPP_API_URL | URL for WhatsApp API service | http://localhost:3000/api |
| QUERY_PREFIX | Command prefix for AI interaction | /query |
| GOOGLE_API_KEY | API key for Google Gemini AI | Required |
| GOOGLE_GENAI_USE_VERTEXAI | Use Vertex AI instead of Gemini API | false |
| AGENT_MODEL | Gemini AI model to use | gemini-2.0-flash |

## Usage

### Basic Commands

```bash
# Start all services
make docker-compose-up

# View logs
make docker-compose-logs

# Stop services
make docker-compose-down
```
## Troubleshooting

### Common Issues

1. **Session Data Issues**
   - Location: `whatsapp-session-data/`
   - Solution: Remove directory and restart services

2. **Service Start Failures**
   - Check logs: `make docker-compose-logs`
   - Verify API keys in `.env`
   - Check webhook configuration

3. **QR Code Authentication**
   - Ensure WhatsApp API service is running
   - Check logs for QR code display
   - Verify session data permissions

4. **Scheduled Messages Not Working**
   - Check cron service status: `docker exec -it <container_name> service cron status`
   - View cron logs: `docker exec -it <container_name> tail -f /var/log/syslog | grep CRON`
   - Verify scheduled tasks: `docker exec -it <container_name> crontab -l`

### Debugging

1. Check service logs:
```bash
make docker-compose-logs
```

2. Verify service health:
```bash
curl http://localhost:8000/health
```

## License and Acknowledgments

- **License**: MIT
- **WhatsApp Integration**: [wweb-mcp](https://github.com/pnizer/wweb-mcp) (forked) and [whatsapp-web.js](https://github.com/pedroslopez/whatsapp-web.js)
- **AI Framework**: Google Gemini AI
- **Containerization**: Docker and Docker Compose