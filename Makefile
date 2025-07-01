# Detect which docker compose command is available
DOCKER_COMPOSE_CMD := $(shell command -v docker-compose 2>/dev/null)
ifeq ($(DOCKER_COMPOSE_CMD),)
    DOCKER_COMPOSE := docker compose
else
    DOCKER_COMPOSE := docker-compose
endif

# Default target
.PHONY: all
all: help

# Help target
.PHONY: help
help:
	@echo "Available commands:"
	@echo "  make up   - Run all services using Docker Compose"
	@echo "  make down - Stop all services"
	@echo "  make logs - View logs from all services"
	@echo "Using: $(DOCKER_COMPOSE)"

# Docker Compose commands
.PHONY: up
up:
	$(DOCKER_COMPOSE) up --build webhook whatsapp-api whatsapp-mcp

.PHONY: down
down:
	$(DOCKER_COMPOSE) down

.PHONY: logs
logs:
	$(DOCKER_COMPOSE) logs -f

