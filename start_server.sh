#!/bin/bash

echo "Starting Invisible AI Server..."
echo ""

cd "$(dirname "$0")"
source venv/bin/activate
python -u server/main_server.py
