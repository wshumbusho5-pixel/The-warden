#!/bin/bash

echo "Starting Invisible AI Client..."
echo ""

cd "$(dirname "$0")"
source venv/bin/activate
python client/agent.py $@
