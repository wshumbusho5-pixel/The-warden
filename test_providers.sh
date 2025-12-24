#!/bin/bash
# Test AI Provider Setup
# This script tests which AI providers are available and working

echo "=========================================="
echo "  Testing AI Provider Setup"
echo "=========================================="
echo ""

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
else
    echo "❌ Virtual environment not found. Run ./setup.sh first"
    exit 1
fi

# Change to server directory
cd server

# Run the provider test
echo ""
echo "Testing AI providers..."
echo "----------------------------------------"
python3 ai_providers.py

echo ""
echo "=========================================="
echo "Test complete!"
echo "=========================================="
