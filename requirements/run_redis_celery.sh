#!/bin/bash

# =========================
# Docker setup for Centryx
# =========================

# Path to your Django project (where manage.py is)
PROJECT_DIR=$(pwd)/Centryx  

REDIS_CONTAINER_NAME="centryx_redis"
CELERY_CONTAINER_NAME="centryx_celery"
NETWORK_NAME="centryx_network"

# -------------------------
# Create Docker network if it doesn't exist
# -------------------------
if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    echo "🌐 Creating Docker network: $NETWORK_NAME"
    docker network create "$NETWORK_NAME"
fi

# -------------------------
# Stop & remove existing Redis container
# -------------------------
if [ "$(docker ps -a -q -f name=$REDIS_CONTAINER_NAME)" ]; then
    echo "🛑 Stopping and removing existing Redis container..."
    docker rm -f "$REDIS_CONTAINER_NAME"
fi

# -------------------------
# Stop & remove existing Celery container
# -------------------------
if [ "$(docker ps -a -q -f name=$CELERY_CONTAINER_NAME)" ]; then
    echo "🛑 Stopping and removing existing Celery container..."
    docker rm -f "$CELERY_CONTAINER_NAME"
fi

# -------------------------
# Run Redis container
# -------------------------
echo "🚀 Starting Redis..."
docker run -d \
    --name "$REDIS_CONTAINER_NAME" \
    --network "$NETWORK_NAME" \
    -p 6379:6379 \
    redis:7

# -------------------------
# Run Celery worker container
# -------------------------
echo "🚀 Starting Celery worker..."
docker run -d \
    --name "$CELERY_CONTAINER_NAME" \
    --network "$NETWORK_NAME" \
    -v "$PROJECT_DIR":/app \
    -w /app \
    -e CELERY_BROKER_URL="redis://$REDIS_CONTAINER_NAME:6379/0" \
    python:3.12-slim \
    bash -c "\
        pip install --no-cache-dir -r /app/requirements.txt && \
        celery -A Centryx worker --loglevel=info"

# -------------------------
# Status message
# -------------------------
echo "✅ Redis and Celery worker are running in Docker"
echo "🔹 Redis container: $REDIS_CONTAINER_NAME"
echo "🔹 Celery container: $CELERY_CONTAINER_NAME"
echo "🔹 Network: $NETWORK_NAME"
