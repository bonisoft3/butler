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

# Function to check if we have sudo access
check_sudo() {
    if ! command_exists sudo; then
        print_message "Error: sudo is not installed" "$RED"
        exit 1
    fi
    if ! sudo -v >/dev/null 2>&1; then
        print_message "Error: No sudo access" "$RED"
        exit 1
    fi
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

# Check if docker and docker-compose are installed
if ! command_exists docker || ! command_exists docker-compose; then
    print_message "Error: docker and docker-compose must be installed" "$RED"
    exit 1
fi

# Check sudo access
check_sudo

# Step 1: Remove existing session data
print_message "Step 1: Cleaning up existing session data..." "$YELLOW"
if [ -d "whatsapp-session-data" ]; then
    print_message "Removing existing whatsapp-session-data directory..." "$YELLOW"
    sudo rm -rf whatsapp-session-data
fi

# Create directory with correct permissions
mkdir -p whatsapp-session-data
sudo chown -R $(id -u):$(id -g) whatsapp-session-data

# Step 2: Start whatsapp-api service
print_message "\nStep 2: Starting WhatsApp API service..." "$YELLOW"
print_message "Please wait for the QR code to appear..." "$GREEN"
print_message "🤖 The Butler is getting ready to connect..." "$GREEN"
docker-compose up whatsapp-api

# Step 3: Extract API key from logs
print_message "\nStep 3: Extracting API key..." "$YELLOW"
API_KEY=$(docker-compose logs whatsapp-api | grep "WhatsApp API key:" | tail -n 1 | awk '{print $NF}')

if [ -z "$API_KEY" ]; then
    print_message "Error: Could not find API key in logs" "$RED"
    exit 1
fi

print_message "API Key found: $API_KEY" "$GREEN"

# Update .env file with the API key
print_message "Updating .env file with the API key..." "$YELLOW"
update_env_file "WHATSAPP_API_KEY" "$API_KEY"
print_message ".env file updated successfully" "$GREEN"

# Step 4: Stop the service
print_message "\nStep 4: Stopping services..." "$YELLOW"
docker-compose down

# Step 5: Start all services
print_message "\nStep 5: Starting all services..." "$YELLOW"
print_message "🤖 The Butler is ready to serve!" "$GREEN"
docker-compose up -d

print_message "\nSetup completed successfully!" "$GREEN"
print_message "You can check the logs with: docker-compose logs -f" "$YELLOW"