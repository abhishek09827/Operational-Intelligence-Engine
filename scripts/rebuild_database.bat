@echo off
REM Script to rebuild the PostgreSQL database with updated schema
REM This script will drop the database and recreate it with the new dimension settings

echo WARNING: This will delete all existing data in the database!
echo.
set /p confirm="Are you sure you want to proceed? (yes/no): "

if not "%confirm%"=="yes" (
    echo Operation cancelled.
    exit /b 1
)

echo.
echo Stopping database container...
docker-compose stop db

echo.
echo Removing database volume...
docker-compose down -v

echo.
echo Starting database with new schema...
docker-compose up -d db

echo.
echo Waiting for database to be ready...
timeout /t 10 /nobreak >nul

echo.
echo Applying initialization scripts...
docker-compose exec -T db psql -U opsuser -d opspilot < docker\init.sql

echo.
echo Database rebuilt successfully!
echo.
echo Note: You may need to restart the application containers:
echo   docker-compose restart app-1 app-2 app-3