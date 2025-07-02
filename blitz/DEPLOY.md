# BlitzAgent Agno - Render Deployment Guide

This guide covers how to deploy BlitzAgent Agno to Render as a production API.

## 🎯 What You Get

After deployment, you'll have:

1. **CLI Access**: Run `blitz chat` locally for interactive chat
2. **Playground Access**: Run `blitzagent-playground` locally for web interface  
3. **Production API**: Deployed on Render for external API calls

## 🚀 Render Deployment Steps

### 1. Prepare Your Repository

Make sure your code is pushed to GitHub with these files:
- `Dockerfile` ✅
- `requirements.txt` ✅  
- `start.sh` ✅
- `src/blitzagent_agno/production_app.py` ✅

### 2. Create Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your GitHub repository
4. Choose the `blitz` folder as the root directory

### 3. Configure Build & Deploy Settings

In the Render console, set these values:

**Build & Deploy:**
- **Environment**: `Docker`
- **Dockerfile Path**: `Dockerfile` (leave as default)
- **Build Command**: (leave empty, handled by Dockerfile)
- **Start Command**: `./start.sh`

**Service Details:**
- **Name**: `blitzagent-api` (or your preferred name)
- **Region**: Choose closest to your users
- **Branch**: `main` (or your preferred branch)
- **Instance Type**: `Starter` (you can upgrade later)

### 4. Environment Variables

Set these environment variables in Render:

#### Required Variables:
```bash
# Model Configuration (choose one)
MODEL_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here

# OR for OpenAI:
# MODEL_PROVIDER=openai  
# OPENAI_API_KEY=your_openai_api_key_here

# Runtime
ENVIRONMENT=production
PORT=8000
```

#### Optional Variables:
```bash
# For debugging
LOG_LEVEL=INFO

# If using database features (advanced)
# DATABASE_URL=postgresql://user:pass@host:5432/db
```

### 5. Deploy

1. Click "Create Web Service"
2. Render will automatically build and deploy
3. Wait for deployment to complete (usually 5-10 minutes)
4. Your API will be available at: `https://your-service-name.onrender.com`

## 🧪 Testing Your Deployment

### Test Health Endpoint
```bash
curl https://your-service-name.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "BlitzAgent API", 
  "version": "1.0.0",
  "timestamp": "2024-01-01T12:00:00.000000",
  "model": "gemini"
}
```

### Test API Query
```bash
curl -X POST https://your-service-name.onrender.com/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello, what can you help me with?",
    "user_id": "test_user"
  }'
```

### View API Documentation
Visit: `https://your-service-name.onrender.com/docs`

## 🔧 Local Development & Testing

### CLI Usage
```bash
cd blitz
pip install -e .

# Interactive chat
blitz chat

# Single query  
blitz query "What are some key baseball statistics?"

# With specific user/session
blitz chat --user test_user --session session_123
```

### Playground Usage
```bash
cd blitz
pip install -e .

# Start playground (opens in browser)
blitzagent-playground
```

### Local API Server
```bash
cd blitz
pip install -e .

# Start local API server
python -m blitzagent_agno.production_app
# Or
uvicorn blitzagent_agno.production_app:app --reload
```

## 📡 Making API Calls from Your Frontend

### JavaScript Example
```javascript
const response = await fetch('https://your-service-name.onrender.com/api/query', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    message: 'Analyze the latest baseball statistics',
    user_id: 'user_123',
    session_id: 'session_456'
  })
});

const data = await response.json();
console.log(data.response);
```

### Python Example
```python
import requests

response = requests.post(
    'https://your-service-name.onrender.com/api/query',
    json={
        'message': 'What are the top MLB teams this season?',
        'user_id': 'user_123',
        'session_id': 'session_456'
    }
)

print(response.json()['response'])
```

### cURL Example
```bash
curl -X POST https://your-service-name.onrender.com/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Tell me about recent NBA games",
    "user_id": "user_123", 
    "session_id": "session_456"
  }'
```

## 🔐 API Endpoints

- **GET** `/` - Service information
- **GET** `/health` - Health check
- **POST** `/api/query` - Query the agent
- **GET** `/api/info` - API information  
- **GET** `/docs` - Interactive API documentation
- **GET** `/redoc` - Alternative API documentation

## 🔍 Troubleshooting

### Common Issues:

1. **Build Fails**: Check that all dependencies are in `requirements.txt`
2. **Agent Not Initialized**: Verify environment variables are set correctly
3. **API Key Issues**: Make sure `GEMINI_API_KEY` or `OPENAI_API_KEY` is properly set
4. **Port Issues**: Render automatically sets `PORT`, don't override it

### Checking Logs:
1. Go to your Render service dashboard
2. Click on "Logs" tab to see real-time logs
3. Look for initialization errors or API key issues

### Environment Variables:
Make sure you've set the required environment variables in the Render dashboard under "Environment" tab.

## 🎉 Success!

Once deployed, you'll have:
- ✅ Production API running on Render
- ✅ CLI tools for local development
- ✅ Playground for interactive testing
- ✅ Full FastAPI documentation at `/docs`

Your BlitzAgent is now ready for production use! 