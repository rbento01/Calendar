#!/bin/bash
set -e  # Exit if any command fails

echo "🚀 Starting Calendar App..."

docker compose down
docker compose build
docker compose up -d

echo "✅ App running at http://localhost:5000"