FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and tini
RUN apt-get update && apt-get install -y \
    build-essential curl cron tini \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Expose the webhook port
EXPOSE 8000

# Use tini as entrypoint
ENTRYPOINT ["/usr/bin/tini", "--"]

# Start both cron and webhook server
CMD ["sh", "-c", "cron && python webhook_server.py"]