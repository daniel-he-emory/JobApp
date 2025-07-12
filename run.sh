#!/bin/bash
# Autonomous Job Application Agent - Run Script
# This script automatically activates the virtual environment and runs the agent

set -e

# Check if virtual environment exists
if [ ! -d "job_agent_env" ]; then
    echo "❌ Virtual environment not found. Please run ./setup.sh first."
    exit 1
fi

# Activate virtual environment
source job_agent_env/bin/activate

# Run the agent with all passed arguments
python main.py "$@"