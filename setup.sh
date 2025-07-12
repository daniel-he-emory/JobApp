#!/bin/bash
# Autonomous Job Application Agent - Quick Setup Script
# This script sets up the virtual environment and installs all dependencies

set -e  # Exit on any error

echo "🚀 Setting up Autonomous Job Application Agent..."

# Check Python version
python3 --version >/dev/null 2>&1 || { echo "❌ Python 3 is required but not installed. Please install Python 3.8+ and try again."; exit 1; }

# Create virtual environment if it doesn't exist
if [ ! -d "job_agent_env" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv job_agent_env
fi

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source job_agent_env/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📥 Installing Python dependencies..."
pip install -r requirements.txt

# Install Playwright browsers
echo "🌐 Installing Playwright browsers..."
playwright install chromium

# Create necessary directories
echo "📁 Creating required directories..."
mkdir -p logs data config

# Copy config template if it doesn't exist
if [ ! -f "config/my_config.yaml" ] && [ -f "config/config.yaml" ]; then
    echo "📋 Creating config template..."
    cp config/config.yaml config/my_config.yaml
    echo "⚠️  Please edit config/my_config.yaml with your credentials before running!"
fi

echo "✅ Setup complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Edit config/my_config.yaml with your credentials"
echo "2. Run: source job_agent_env/bin/activate"
echo "3. Test: python main.py --dry-run --verbose"
echo "4. Run: python main.py --platforms linkedin --max-apps 1"
echo ""
echo "💡 To always activate the virtual environment automatically, add this to your shell profile:"
echo "   alias jobapp='cd $(pwd) && source job_agent_env/bin/activate'"