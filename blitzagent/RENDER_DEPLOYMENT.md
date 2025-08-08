# Render Deployment Guide for Blitz

This guide helps you deploy Blitz to Render with robust handling of network issues and dependencies.

## 🚀 Quick Setup

### Option 1: Using Start Script (Recommended)

1. **Create a Web Service** in Render
2. **Connect your GitHub repository**
3. **Configure the service**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `./render_start.sh`
   - **Environment**: `Python 3.11`

### Option 2: Using Docker

1. **Create a Web Service** in Render
2. **Set Runtime**: Docker
3. **No build/start commands needed** (uses Dockerfile)

## 🔧 Environment Variables

Set these in your Render dashboard:

| Variable | Description | Example |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | **Required** - Your Anthropic API key | `sk-ant-api03-...` |
| `API_KEY` | **Required** - Your Blitz API authentication key | `your-secure-api-key` |
| `HOST` | Server host (leave default) | `0.0.0.0` |
| `PORT` | Server port (leave default) | `10000` |
| `LOG_LEVEL` | Logging level | `INFO` |

## 🔧 Troubleshooting Deployment Issues

### Connection Reset Errors

The error you encountered is typically caused by network timeouts during pip install. Here are the solutions we've implemented:

#### 1. **Removed Git Dependency from requirements.txt**
```diff
- git+https://github.com/tejassrinivasan/BlitzLLM.git#subdirectory=mcp
```
We moved this to the startup script to handle it more gracefully.

#### 2. **Enhanced Start Script** (`render_start.sh`)
- Installs MCP package at runtime with timeout handling
- Graceful fallback if git dependency fails
- Environment validation before startup

#### 3. **Multi-stage Docker Build** (Alternative)
- Pre-builds all dependencies as wheels
- Reduces network requests during deployment
- More reliable for complex dependencies

### Build Failures

If builds continue to fail:

#### **Strategy 1: Retry Deployment**
Network issues are often temporary. Try deploying again.

#### **Strategy 2: Use Docker**
Switch to Docker deployment which is more reliable:
1. In Render dashboard, change **Runtime** to "Docker"
2. Clear build/start commands
3. Redeploy

#### **Strategy 3: Simplify Dependencies**
If issues persist, temporarily remove the MCP git dependency:
1. Comment out MCP installation in `render_start.sh`
2. Deploy successfully first
3. Add MCP back later via manual install

### Runtime Issues

#### **MCP Connection Failures**
If the MCP package fails to install:
- The app will still start (graceful fallback)
- Some advanced features may be limited
- Check logs for specific error messages

#### **Environment Variable Issues**
```bash
# Check if variables are set correctly
echo $ANTHROPIC_API_KEY
echo $API_KEY
```

Common fixes:
- Ensure no extra spaces in variable values
- Check for special characters that need escaping
- Verify keys are active and have sufficient credits

## 📋 Step-by-Step Deployment

### 1. Prepare Repository
Ensure these files are in your repository:
- ✅ `requirements.txt` (simplified, no git dependencies)
- ✅ `render_start.sh` (robust startup script)
- ✅ `Dockerfile` (optional, for Docker deployment)
- ✅ `.dockerignore` (optimizes Docker builds)

### 2. Create Render Service
1. **Go to** [Render Dashboard](https://dashboard.render.com)
2. **Click** "New +" → "Web Service"
3. **Connect** your GitHub repository
4. **Select** the `blitzagent` directory

### 3. Configure Service
```yaml
# Basic Configuration
Name: blitz-api
Runtime: Python 3.11
Build Command: pip install -r requirements.txt
Start Command: ./render_start.sh

# Advanced Configuration
Auto-Deploy: Yes
Health Check Path: /health
```

### 4. Set Environment Variables
In the Render dashboard:
1. **Go to** Environment tab
2. **Add** required variables:
   ```
   ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
   API_KEY=your-blitz-api-key-here
   LOG_LEVEL=INFO
   ```

### 5. Deploy
1. **Click** "Create Web Service"
2. **Wait** for build to complete (5-10 minutes)
3. **Check** deployment logs for any issues

### 6. Verify Deployment
Test your deployed API:
```bash
# Health check
curl https://your-app-name.onrender.com/health

# Test analysis (replace YOUR_API_KEY with the value you set)
curl -X POST "https://your-app-name.onrender.com/analyze" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Test deployment with LeBron James stats"}'
```

## 🐋 Docker Deployment (Alternative)

If you prefer Docker or encounter build issues:

### 1. Switch to Docker
1. **In Render dashboard**, go to Settings
2. **Change Runtime** to "Docker"
3. **Clear** Build and Start commands
4. **Save** and redeploy

### 2. Docker Benefits
- ✅ More reliable dependency installation
- ✅ Consistent build environment
- ✅ Pre-compiled dependencies
- ✅ Faster startup times

## 🔍 Monitoring & Logs

### Health Checks
Render automatically monitors your app using the `/health` endpoint:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-20T10:30:00Z",
  "version": "1.0.0"
}
```

### Log Monitoring
Monitor these key log messages:
- ✅ `Starting Blitz server...` - App is starting
- ✅ `Environment validated` - Configuration is correct
- ✅ `Server started successfully` - Ready for requests
- ⚠️ `Warning: Failed to install MCP package` - Limited functionality
- ❌ `ANTHROPIC_API_KEY is not set` - Configuration error

### Performance Tips
1. **Use appropriate instance size** for your traffic
2. **Enable autoscaling** if traffic varies
3. **Monitor response times** via Render metrics
4. **Set up alerts** for downtime or errors

## 🆘 Still Having Issues?

### Debug Build Process
Enable verbose logging during build:
```bash
# Add to render_start.sh for debugging
set -x  # Enable debug output
pip install -v --no-cache-dir -r requirements.txt
```

### Contact Support
If issues persist:
1. **Check** [Render Status](https://status.render.com/)
2. **Review** deployment logs in dashboard
3. **Contact** Render support with specific error messages
4. **Share** logs from the deployment process

### Alternative Hosting
Consider these alternatives if Render continues to have issues:
- **Railway** - Similar to Render, git-based deployment
- **Fly.io** - Docker-focused, good for complex apps
- **Google Cloud Run** - Serverless container deployment
- **AWS App Runner** - Container-based deployment

## 📊 Production Configuration

### Scaling
For production workloads:
```yaml
# Render Service Configuration
Instance Type: Starter (1GB RAM) or higher
Auto-scaling: Enable
Min Instances: 1
Max Instances: 10
```

### Security
- ✅ Use strong, unique API keys
- ✅ Rotate keys regularly
- ✅ Monitor usage patterns
- ✅ Set up alerts for unusual activity

### Monitoring
Set up monitoring for:
- Response time latency
- Error rates
- API usage patterns
- Resource utilization

The deployment should now be much more robust and handle network issues gracefully! 🚀
