#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_message() {
    echo -e "${2}${1}${NC}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to update .env file
update_env_file() {
    local key=$1
    local value=$2
    local env_file=".env"

    # Create .env if it doesn't exist
    if [ ! -f "$env_file" ]; then
        touch "$env_file"
    fi

    # Check if the key exists in the file
    if grep -q "^${key}=" "$env_file"; then
        # Update existing key
        sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
    else
        # Add new key
        echo "${key}=${value}" >> "$env_file"
    fi
}

# Check if docker and docker compose plugin are installed
if ! command_exists docker; then
    print_message "Error: docker must be installed" "$RED"
	exit 1
elif ! command_exists docker compose; then
    print_message "Error: docker compose plugin must be installed" "$RED"
	exit 1
fi

# Step 1: Remove existing session data
print_message "Step 1: Cleaning up existing session data..." "$YELLOW"
if [ -d "whatsapp-session-data" ]; then
    print_message "Removing existing whatsapp-session-data directory..." "$YELLOW"
    rm -rf whatsapp-session-data
fi

mkdir -p whatsapp-session-data
cp webhook.json ./whatsapp-session-data

# Step 2: Start WhatsApp API service to generate session data
print_message "\nStep 2: Starting WhatsApp API service..." "$YELLOW"
print_message "🤖 The Butler is getting ready to connect..." "$GREEN"
print_message "Waiting for WhatsApp API to be ready..." "$YELLOW"
docker compose up -d --build whatsapp-api

timeout=60
interval=2
elapsed=0
# Loop waits until "WhatsApp Web Client API started successfully" appears in the logs
while ! docker compose logs whatsapp-api 2>/dev/null | grep -q "WhatsApp Web Client API started successfully"; do
  if [ "$elapsed" -ge "$timeout" ]; then
    print_message "Timeout reached waiting for WhatsApp API to be ready." "$RED"
    exit 1
  fi
  sleep "$interval"
  elapsed=$((elapsed + interval))
done

# Step 3: Extract API key from logs
print_message "\nStep 3: Extracting API key..." "$YELLOW"
API_KEY=$(cat ./whatsapp-session-data/api_key.txt)

if [ -z "$API_KEY" ]; then
    print_message "Error: Could not find API key in session data" "$RED"
    exit 1
fi

print_message "API Key found: $API_KEY" "$GREEN"

# Update .env file with the API key
print_message "Updating .env file with the API key..." "$YELLOW"
update_env_file "WHATSAPP_API_KEY" "$API_KEY"
print_message ".env file updated successfully" "$GREEN"

# Step 4: Stop the service
print_message "\nStep 4: Stopping services..." "$YELLOW"
docker compose down

print_message "\nSetup completed successfully!" "$GREEN"
print_message "Now you can startup Butler by running 'make up' and scan the QR code with your phone." "$YELLOW"

