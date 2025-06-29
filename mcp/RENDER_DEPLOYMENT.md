# Render Deployment Guide for Blitz Agent MCP Server

This guide provides step-by-step instructions for deploying your MCP server to Render.

## Prerequisites

- A Render account (free tier available)
- Your code pushed to GitHub/GitLab/Bitbucket
- Environment variables configured

## Render Configuration

### 1. Create New Web Service

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click "New +" → "Web Service"
3. Connect your repository containing the MCP code

### 2. Service Configuration

**Basic Settings:**
- **Name**: `blitz-agent-mcp-server`
- **Environment**: `Python 3`
- **Region**: Choose your preferred region
- **Branch**: `main` (or your deployment branch)
- **Root Directory**: `mcp` (if MCP is in a subdirectory)

**Build & Deploy Settings:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `./start_render.sh`

### 3. Environment Variables

Add these environment variables in Render dashboard under "Environment":

#### Required Database Configuration
```
POSTGRES_HOST=your-postgres-host
POSTGRES_PORT=5432
POSTGRES_DATABASE=your-db-name
POSTGRES_USER=your-username
POSTGRES_PASSWORD=your-password
POSTGRES_SSL=true
```

#### Optional API Keys (for enhanced functionality)
```
BLITZ_API_KEY=your-api-key
FIRECRAWL_API_KEY=your-firecrawl-key
AZURE_SEARCH_ENDPOINT=your-azure-search-endpoint
AZURE_SEARCH_API_KEY=your-azure-search-key
AZURE_SEARCH_INDEX_NAME=your-index-name
AZURE_OPENAI_API_KEY=your-azure-openai-key
AZURE_OPENAI_ENDPOINT=your-azure-openai-endpoint
COSMOS_DB_ENDPOINT=your-cosmos-endpoint
COSMOS_DB_KEY=your-cosmos-key
SPORTSDATA_API_KEY=your-sportsdata-key
```

#### Render-Specific Variables
```
RENDER=true
```

### 4. Advanced Settings

**Health Check Path**: `/health`
- The server now includes health check endpoints at `/` and `/health`
- Render will automatically detect your service is healthy

**Auto-Deploy**: Enable this to automatically deploy when you push to your repository

## Deployment Process

1. **Initial Deploy**: Click "Create Web Service" - this will trigger the initial build and deployment
2. **Monitor Logs**: Watch the deploy logs for any issues
3. **Health Check**: Render will perform health checks on your endpoints
4. **Access URL**: Once deployed, you'll get a URL like `https://your-service-name.onrender.com`

## Testing Your Deployment

Once deployed, you can test your endpoints:

```bash
# Health check
curl https://your-service-name.onrender.com/health

# Basic status
curl https://your-service-name.onrender.com/
```

Expected response:
```json
{
  "status": "ok",
  "service": "Blitz Agent MCP Server",
  "version": "1.0.0"
}
```

## Troubleshooting

### Common Issues

1. **Build Fails**: Check that all dependencies in `requirements.txt` are correct
2. **Health Check Fails**: Ensure your service starts and binds to `0.0.0.0:$PORT`
3. **Database Connection**: Verify all PostgreSQL environment variables are set correctly
4. **Memory Issues**: Consider upgrading to a paid plan if using large ML libraries

### Logs Access

View real-time logs in Render dashboard:
1. Go to your service
2. Click "Logs" tab
3. Monitor for startup issues

### Port Configuration

The server automatically:
- Uses `PORT` environment variable provided by Render
- Binds to `0.0.0.0` (all interfaces) when `RENDER=true`
- Provides health check endpoints for monitoring

## Production Considerations

### Security
- Never commit API keys to your repository
- Use Render's environment variables for all secrets
- Enable SSL (automatic with Render)

### Performance
- Consider upgrading to a paid plan for better performance
- Monitor resource usage in Render dashboard
- Optimize database queries for better response times

### Monitoring
- Set up alerts in Render dashboard
- Monitor health check endpoint status
- Review error logs regularly

## Support

If you encounter issues:
1. Check the deployment logs in Render dashboard
2. Verify all environment variables are set
3. Test health endpoints manually
4. Review this guide for missing configuration

Your MCP server should now be successfully deployed and accessible via the Render-provided URL! 