# Twitter Mention Listener Bot

A Twitter bot that listens for mentions and responds using the BlitzAgent API for sports-related queries.

## Features

- Listens for Twitter mentions in real-time
- Detects explicit mentions to avoid spam
- Provides sports analysis using BlitzAgent API
- Keeps responses under 250 characters for Twitter
- Includes thread context and comment highlights

## Setup

1. **Environment Variables**: Create a `.env` file with:
```
# Twitter API Credentials
X_BEARER_TOKEN=your_bearer_token
X_CONSUMER_KEY=your_consumer_key
X_CONSUMER_SECRET=your_consumer_secret
X_ACCESS_TOKEN=your_access_token
X_ACCESS_SECRET=your_access_secret
X_BOT_NAME=@YourBotName

# BlitzAgent API
BLITZAGENT_API_KEY=your_blitzagent_api_key
```

2. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

3. **Run the Bot**:
```bash
./start.sh
```

## Deployment

This bot is designed to run as a background worker on Render or similar platforms. The `start.sh` script handles dependency installation and environment validation.

For Render deployment:
- Set the start command to: `./start.sh`
- Configure all environment variables in the Render dashboard
- The bot will run continuously, checking for mentions every 60 seconds

## How It Works

1. **Mention Detection**: Scans for mentions using Twitter API v2
2. **Context Gathering**: Collects thread context and top replies 
3. **BlitzAgent Query**: Sends sports query to BlitzAgent with Twitter context
4. **Response**: Posts concise reply using sports analytics

## Error Handling

- Validates all required environment variables on startup
- Handles API rate limits with built-in waiting
- Graceful error handling for network issues
- Automatic truncation if responses exceed character limits 