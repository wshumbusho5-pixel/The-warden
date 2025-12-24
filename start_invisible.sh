#!/bin/bash

echo "Starting Invisible AI Assistant (Full Featured)..."
echo ""

cd "$(dirname "$0")"
source venv/bin/activate

# Run in background mode by default
python client/invisible_agent.py --mode background $@
