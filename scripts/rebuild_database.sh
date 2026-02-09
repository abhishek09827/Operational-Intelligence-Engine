#!/bin/bash

# Script to rebuild the PostgreSQL database with updated schema
# This script will drop the database and recreate it with the new dimension settings

echo "⚠️  WARNING: This will delete all existing data in the database!"
echo ""
read -p "Are you sure you want to proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Operation cancelled."
    exit 1
fi

echo ""
echo "Stopping database container..."
docker-compose stop db

echo ""
echo "Removing database volume..."
docker-compose down -v

echo ""
echo "Starting database with new schema..."
docker-compose up -d db

echo ""
echo "Waiting for database to be ready..."
sleep 10

echo ""
echo "Applying initialization scripts..."
docker-compose exec -T db psql -U opsuser -d opspilot < docker/init.sql

echo ""
echo "✅ Database rebuilt successfully!"
echo ""
echo "Note: You may need to restart the application containers:"
echo "  docker-compose restart app-1 app-2 app-3"