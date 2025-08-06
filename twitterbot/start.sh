#!/bin/bash
"""
Startup script for Twitter Mention Listener Bot
Handles dependency installation and service startup.
"""

set -e  # Exit on any error

echo "🤖 Starting Twitter Mention Listener Bot"
echo "========================================"

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}' | cut -d. -f1,2)
echo "Python version: $python_version"

if [[ $(echo "$python_version >= 3.8" | bc -l) -eq 0 ]]; then
    echo "❌ Error: Python 3.8+ required, found $python_version"
    exit 1
fi

# Install dependencies if needed
if [ ! -f ".last_install" ] || [ "requirements.txt" -nt ".last_install" ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    touch .last_install
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already up to date"
fi

# Check required environment variables
echo "🔧 Checking configuration..."

if [ -z "$BLITZAGENT_API_KEY" ]; then
    echo "❌ Error: BLITZAGENT_API_KEY environment variable is required"
    echo "   Get your API key from BlitzAgent service"
    exit 1
fi

if [ -z "$X_BEARER_TOKEN" ]; then
    echo "❌ Error: X_BEARER_TOKEN environment variable is required"
    echo "   Get your Twitter API credentials from https://developer.twitter.com/"
    exit 1
fi

if [ -z "$X_CONSUMER_KEY" ] || [ -z "$X_CONSUMER_SECRET" ] || [ -z "$X_ACCESS_TOKEN" ] || [ -z "$X_ACCESS_SECRET" ]; then
    echo "❌ Error: Twitter API credentials incomplete"
    echo "   Required: X_CONSUMER_KEY, X_CONSUMER_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET"
    exit 1
fi

if [ -z "$X_BOT_NAME" ]; then
    echo "❌ Error: X_BOT_NAME environment variable is required"
    echo "   Set this to your bot's Twitter username (e.g., @MyBot)"
    exit 1
fi

echo "✅ BLITZAGENT_API_KEY configured"
echo "✅ Twitter API credentials configured"
echo "✅ Bot username: $X_BOT_NAME"

echo ""
echo "🚀 Starting Twitter Mention Listener"
echo "   Bot will listen for mentions and reply using BlitzAgent"
echo "   Use Ctrl+C to stop"
echo ""

python twitter_bot.py 