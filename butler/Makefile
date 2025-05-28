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


# Docker Compose commands
.PHONY: docker-compose-up
up:
	docker-compose up --build webhook whatsapp-api whatsapp-mcp

.PHONY: docker-compose-down
down:
	docker-compose down

.PHONY: docker-compose-logs
logs:
	docker-compose logs -f
