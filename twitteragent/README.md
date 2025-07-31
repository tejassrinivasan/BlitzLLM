# Twitter NBA Agent

Automated NBA content discovery and analytics posting system using **Pydantic AI Framework** and **Claude 4 Sonnet**.

## 🏀 Overview

This Twitter NBA Agent replicates the functionality of the production NBA workflow but uses the modern **pydantic-ai** framework instead of agno workflows. It:

1. **Discovers trending NBA content** on Twitter
2. **Generates smart analytics questions** about basketball
3. **Posts questions** from @tejsri01 account  
4. **Generates comprehensive analytics** using the same MCP tools as blitzagent
5. **Posts responses** from @BlitzAIBot account
6. **Runs automatically 6 times per day**

## 🚀 Key Features

- **Claude 4 Sonnet Integration**: Uses the same advanced reasoning model as blitzagent
- **Pydantic AI Framework**: Modern agent framework with type safety and validation
- **MCP Tools Integration**: Same sports analytics tools as blitzagent (database, web scraping, betting data)
- **Twitter Automation**: Full Twitter workflow with multiple account management
- **Background Worker**: Scheduled execution 6 times daily
- **FastAPI Monitoring**: REST API for monitoring and control
- **Comprehensive Logging**: Detailed execution tracking and error handling

## 📋 Workflow Steps

### **Complete NBA Twitter Automation:**

1. **🔍 NBA Content Discovery** - Search Twitter for trending NBA content using BlitzAnalytics account
2. **⭐ Content Scoring** - AI-powered engagement scoring and selection of best content  
3. **🤖 Question Generation** - Generate engaging, data-driven questions
4. **📱 Question Posting** - Post question from @tejsri01 account (as reply or standalone)
5. **📊 NBA Analytics** - Generate comprehensive responses using MCP tools:
   - Historical Database (PostgreSQL) - Primary source
   - Web Scraping - Secondary source for recent news
   - Live Betting Data - Tertiary source for odds/props
6. **🤖 Response Posting** - Post analytics reply from @BlitzAIBot account

## 🛠️ Installation & Setup

### **1. Install Dependencies**
```bash
cd twitteragent
pip install -r requirements.txt
```

### **2. Environment Configuration**
Set these environment variables:
```bash
# Anthropic API (required)
export ANTHROPIC_API_KEY="your_anthropic_api_key"

# Twitter API credentials (already configured in config.py)
# Server configuration (optional)
export HOST="0.0.0.0"
export PORT="8002"
export LOG_LEVEL="INFO"

# Worker configuration (optional)
export WORKER_RUNS_PER_DAY="6"  # Runs every 4 hours
```

### **3. MCP Tools**
The agent uses the same MCP tools as blitzagent:
- Ensure `blitz-agent-mcp` package is installed and accessible
- Database credentials are configured in `twitter_agent.py`

## 🚀 Usage

### **Background Worker (Production)**
```bash
# Start the background worker (runs 6 times daily)
python worker.py

# Start with FastAPI monitoring interface
python main.py
```

### **Manual Execution**
```bash
# Run test workflow (no Twitter posting)
python worker.py --test

# Run workflow once (real Twitter posting)
python worker.py --run-once

# Check status
python worker.py --status

# View execution statistics
python worker.py --stats
```

### **FastAPI Monitoring**
The agent provides a REST API at `http://localhost:8002`:

- `GET /` - Basic status
- `GET /health` - Health check
- `GET /status` - Detailed system status
- `POST /execute` - Manual workflow execution
- `POST /test` - Test workflow (no Twitter posting)
- `GET /logs` - Recent execution logs
- `POST /worker/control` - Start/stop/restart worker
- `GET /config` - Current configuration

## 🔧 Configuration

### **Schedule Times (6 times daily)**
- 06:00 AM
- 10:00 AM  
- 02:00 PM
- 06:00 PM
- 10:00 PM
- 02:00 AM

### **Twitter Accounts**
- **@BlitzAnalytics** - Content discovery (rate-limit free)
- **@tejsri01** - Question posting
- **@BlitzAIBot** - Analytics responses (blue check verified)

### **MCP Analytics Pipeline**
Same as blitzagent with priority hierarchy:
1. **Historical Database** (PostgreSQL) - Primary source
2. **Web Scraping** - Recent news and updates
3. **Live Betting Data** - Odds and prop analysis

## 📊 Monitoring & Logs

### **Execution Tracking**
- `execution_log.json` - Detailed execution history
- `worker_status.json` - Current worker status
- `nba_worker.log` - Application logs
- `processed_tweets.json` - Duplicate prevention

### **Success Metrics**
- Execution success rate
- Average execution duration
- Twitter posting success
- MCP tool performance

## 🔄 Deployment (Render)

For background worker deployment on Render:

### **1. Service Configuration**
```yaml
# render.yaml
services:
  - type: background-worker
    name: twitter-nba-agent
    runtime: python3
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python worker.py"
    plan: starter
    env: production
```

### **2. Environment Variables**
Set in Render console:
- `ANTHROPIC_API_KEY`
- `LOG_LEVEL=INFO`
- Any Twitter credential overrides

### **3. Monitoring via FastAPI**
Also deploy a web service for monitoring:
```yaml
  - type: web
    name: twitter-nba-agent-api
    runtime: python3
    buildCommand: "pip install -r requirements.txt"
    startCommand: "python main.py"
    plan: starter
```

## 🆚 Differences from Original NBA Workflow

| Feature | Original (agents/) | New (twitteragent/) |
|---------|-------------------|---------------------|
| **Framework** | Agno Workflows | Pydantic AI |
| **Model** | Azure OpenAI | Claude 4 Sonnet |
| **Agent Architecture** | Workflow steps | Single agent with MCP tools |
| **Configuration** | Multiple files | Single config.py |
| **Monitoring** | Basic logging | FastAPI + detailed tracking |
| **Error Handling** | Basic | Comprehensive retry logic |
| **Type Safety** | Limited | Full Pydantic validation |

## 🎯 Integration with blitzagent

The Twitter NBA agent uses the **exact same MCP tools** as blitzagent:
- Same database connections and credentials
- Same sports analytics prompts and rules
- Same tool hierarchy (DB → Web → Betting)
- Same intelligent retry logic

This ensures **consistent analytics quality** across both systems.

## 🏆 Ready for Production!

The Twitter NBA Agent is production-ready with:
- ✅ Robust error handling and retries
- ✅ Comprehensive logging and monitoring
- ✅ Scheduled execution (6x daily)
- ✅ Rate limit management
- ✅ Duplicate content prevention
- ✅ FastAPI monitoring interface
- ✅ Same analytics quality as blitzagent

Deploy as a background worker in Render console and enjoy automated NBA Twitter engagement! 🚀 