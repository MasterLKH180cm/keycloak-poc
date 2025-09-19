#!/bin/bash

# Docker build and run script for Keycloak stack
# Usage: ./build-and-run.sh [build|run|stop|clean]

set -e

# Configuration
NETWORK_NAME="keycloak-stack"
DB_CONTAINER="keycloak-db"
KEYCLOAK_CONTAINER="keycloak-app"
DB_IMAGE="keycloak-postgres:17.6"
KEYCLOAK_IMAGE="keycloak-app:26.0"

# Environment variables (can be overridden)
POSTGRES_DB=${POSTGRES_DB:-keycloak}
POSTGRES_USER=${POSTGRES_USER:-keycloak}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-keycloak}
KEYCLOAK_ADMIN=${KEYCLOAK_ADMIN:-admin}
KEYCLOAK_ADMIN_PASSWORD=${KEYCLOAK_ADMIN_PASSWORD:-admin}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Create network if it doesn't exist
create_network() {
    if ! docker network inspect $NETWORK_NAME >/dev/null 2>&1; then
        log "Creating Docker network: $NETWORK_NAME"
        docker network create $NETWORK_NAME
    else
        log "Network $NETWORK_NAME already exists"
    fi
}

# Build images
build_images() {
    log "Building PostgreSQL image..."
    docker build -f Dockerfile.postgres -t $DB_IMAGE .
    
    log "Building Keycloak image..."
    docker build -f Dockerfile.keycloak -t $KEYCLOAK_IMAGE .
    
    log "Images built successfully!"
}

# Run containers
run_containers() {
    create_network
    
    # Check if containers are already running
    if docker ps -q -f name=$DB_CONTAINER | grep -q .; then
        warn "Database container is already running"
    else
        log "Starting PostgreSQL container..."
        docker run -d \
            --name $DB_CONTAINER \
            --network $NETWORK_NAME \
            -p 5432:5432 \
            -v keycloak_db_data:/var/lib/postgresql/data \
            -e POSTGRES_DB=$POSTGRES_DB \
            -e POSTGRES_USER=$POSTGRES_USER \
            -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
            -e TZ=UTC \
            --cpus="0.5" \
            --memory="512m" \
            --restart unless-stopped \
            $DB_IMAGE
    fi
    
    # Wait for database to be ready
    log "Waiting for database to be ready..."
    until docker exec $DB_CONTAINER pg_isready -U $POSTGRES_USER -d $POSTGRES_DB; do
        sleep 2
    done
    
    if docker ps -q -f name=$KEYCLOAK_CONTAINER | grep -q .; then
        warn "Keycloak container is already running"
    else
        log "Starting Keycloak container..."
        docker run -d \
            --name $KEYCLOAK_CONTAINER \
            --network $NETWORK_NAME \
            -p 8080:8080 \
            -e KC_BOOTSTRAP_ADMIN_USERNAME=$KEYCLOAK_ADMIN \
            -e KC_BOOTSTRAP_ADMIN_PASSWORD=$KEYCLOAK_ADMIN_PASSWORD \
            -e KC_DB=postgres \
            -e KC_DB_URL=jdbc:postgresql://$DB_CONTAINER:5432/$POSTGRES_DB \
            -e KC_DB_USERNAME=$POSTGRES_USER \
            -e KC_DB_PASSWORD=$POSTGRES_PASSWORD \
            -e TZ=UTC \
            --cpus="1.0" \
            --memory="1024m" \
            --restart unless-stopped \
            $KEYCLOAK_IMAGE
    fi
    
    log "Containers started successfully!"
    log "Keycloak admin console: http://localhost:8080"
    log "Database connection: localhost:5432"
}

# Stop containers
stop_containers() {
    log "Stopping containers..."
    docker stop $KEYCLOAK_CONTAINER $DB_CONTAINER 2>/dev/null || true
    docker rm $KEYCLOAK_CONTAINER $DB_CONTAINER 2>/dev/null || true
    log "Containers stopped and removed"
}

# Clean up everything
clean_all() {
    stop_containers
    log "Removing images..."
    docker rmi $KEYCLOAK_IMAGE $DB_IMAGE 2>/dev/null || true
    log "Removing network..."
    docker network rm $NETWORK_NAME 2>/dev/null || true
    log "Cleanup complete"
}

# Show usage
usage() {
    echo "Usage: $0 [build|run|stop|clean|logs]"
    echo ""
    echo "Commands:"
    echo "  build   - Build Docker images"
    echo "  run     - Run the containers"
    echo "  stop    - Stop and remove containers"
    echo "  clean   - Clean up everything (containers, images, network)"
    echo "  logs    - Show logs for running containers"
    echo ""
    echo "Environment variables:"
    echo "  POSTGRES_DB (default: keycloak)"
    echo "  POSTGRES_USER (default: keycloak)"
    echo "  POSTGRES_PASSWORD (default: keycloak)"
    echo "  KEYCLOAK_ADMIN (default: admin)"
    echo "  KEYCLOAK_ADMIN_PASSWORD (default: admin)"
}

# Show logs
show_logs() {
    echo "=== PostgreSQL logs ==="
    docker logs --tail=50 $DB_CONTAINER 2>/dev/null || echo "DB container not running"
    echo ""
    echo "=== Keycloak logs ==="
    docker logs --tail=50 $KEYCLOAK_CONTAINER 2>/dev/null || echo "Keycloak container not running"
}

# Main script logic
case "${1:-}" in
    build)
        build_images
        ;;
    run)
        run_containers
        ;;
    stop)
        stop_containers
        ;;
    clean)
        clean_all
        ;;
    logs)
        show_logs
        ;;
    *)
        usage
        exit 1
        ;;
esac