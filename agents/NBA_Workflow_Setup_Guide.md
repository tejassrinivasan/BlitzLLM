# NBA Content Discovery Workflow - Setup Guide

## 🏀 Overview

This NBA Content Discovery Workflow uses **Agno Workflows 2.0** to orchestrate a complete automated NBA Twitter analytics system. The workflow runs 6 times daily and creates engaging NBA analytics interactions between @tejsri01 and @BlitzAIBot.

## 📋 Workflow Steps

### **Sequential Execution:**

1. **🔍 NBA Content Discovery** - Search Twitter for trending NBA content
2. **⭐ Content Selection** - AI-powered scoring and selection of best content  
3. **🤖 Question Generation** - Generate engaging, data-driven questions
4. **📱 Question Posting** - Post question from @tejsri01 account
5. **🔧 Question Processing** - Clean and prepare for analytics
6. **📊 NBA Analytics** - Generate data-driven responses using NBA database
7. **💬 Response Preparation** - Format response with proper context
8. **🤖 Response Posting** - Post analytics reply from @BlitzAIBot account

## 🛠️ Installation & Setup

### **1. Install Agno**
```bash
pip install agno>=2.0.0
```

### **2. Install Additional Dependencies**
```bash
pip install -r nba_workflow_requirements.txt
```

### **3. Environment Configuration**
Add to your environment variables:
```bash
export AZURE_OPENAI_API_KEY="your_azure_openai_key"
export AZURE_OPENAI_ENDPOINT="https://blitzgpt.openai.azure.com/"
export AZURE_OPENAI_DEPLOYMENT="gpt-4o"
export AZURE_OPENAI_API_VERSION="2025-03-01-preview"
```

### **4. Replace Mock Tools with Real Implementations**

#### **Twitter Tools** (Replace in `nba_workflow.py`):
```python
def search_nba_tweets(agent: Agent, query: str = "#NBA", max_results: int = 10) -> str:
    """Search for NBA-related tweets using real Twitter MCP client."""
    from twitter_mcp_client import create_twitter_client
    
    async with create_twitter_client() as client:
        tweets = await client.search_tweets(
            query=query,
            max_results=max_results,
            hours_back=24,
            include_media=True
        )
        return json.dumps(tweets, indent=2)

def post_tweet(agent: Agent, text: str, account: str = "tejsri01", reply_to: str = None) -> str:
    """Post tweet using real Twitter MCP client."""
    from twitter_mcp_client import create_twitter_client
    
    async with create_twitter_client() as client:
        response = await client.post_tweet(
            text=text,
            account=account,
            reply_to_tweet_id=reply_to
        )
        return json.dumps(response, indent=2)
```

#### **NBA Database Tools** (Replace in `nba_workflow.py`):
```python
def query_nba_database(agent: Agent, question: str) -> str:
    """Query NBA database using real Blitz MCP client."""
    from blitz_mcp_client import create_blitz_client
    
    async with create_blitz_client() as blitz_client:
        answer = await blitz_client.generate_nba_response(
            user_question=question,
            thread_content=None,
            original_author=None,
            current_author="tejsri01",
            comment_highlights=None
        )
        return answer
```

## 🚀 Running the Workflow

### **Test Single Cycle:**
```bash
python nba_workflow.py
```

### **Production Deployment (6x Daily):**
```python
# Uncomment in nba_workflow.py:
schedule_nba_workflow()
```

**Schedule:** 8AM, 12PM, 4PM, 8PM, 12AM, 4AM daily

## 📊 Workflow Architecture

### **Agents:**
- **NBA Content Discoverer** - Finds trending NBA content
- **NBA Question Generator** - Creates engaging analytics questions  
- **NBA Tweet Poster** - Posts questions from @tejsri01
- **NBA Analytics Specialist** - Generates data-driven answers
- **NBA Response Poster** - Posts replies from @BlitzAIBot

### **Custom Functions:**
- **select_best_nba_content()** - AI-powered content scoring
- **extract_question_for_analytics()** - Question preprocessing
- **prepare_response_with_context()** - Response formatting

### **Tools Available to All Agents:**
- **Twitter Tools:** `search_nba_tweets()`, `post_tweet()`
- **NBA Database Tools:** `query_nba_database()`, `get_nba_trends()`

## 🔄 Data Flow

```
1. Discover NBA Content → JSON tweet data
2. Select Best Content → Selected tweet object
3. Generate Question → @BlitzAIBot question string
4. Post Question → Tweet URL & ID
5. Extract Question → Clean question text
6. Generate Analytics → NBA data analysis
7. Prepare Response → Formatted response with context
8. Post Response → Final reply URL
```

## 📝 Example Workflow Execution

**Input:** `"Discover trending NBA content and create engaging analytics interaction"`

**Step Results:**
1. **Content Discovery:** Found Lakers vs Warriors OT game
2. **Content Selection:** Selected based on engagement score (5,000+ interactions)
3. **Question Generation:** `"@BlitzAIBot How do the Lakers and Warriors compare in overtime win percentage over the last 5 seasons?"`
4. **Question Posting:** Posted to @tejsri01 account
5. **Analytics Generation:** Retrieved historical OT data from NBA database
6. **Response Posting:** Posted comprehensive analytics reply from @BlitzAIBot

## 🎯 Key Features

### **Intelligent Content Selection:**
- Engagement-based scoring (likes + retweets × 2)
- Content bonus for statistical keywords
- AI-powered relevance analysis

### **Balanced Question Generation:**
- Performance comparisons
- Team trends analysis  
- Situational breakdowns
- Betting-related scenarios
- No quotes or emojis (clean format)

### **Data-Driven Analytics:**
- Real NBA historical database queries
- Current trends and projections
- Statistical context and comparisons
- Twitter-optimized formatting

### **Workflow State Management:**
- SQLite storage for workflow sessions
- Step-by-step result tracking
- Error handling and recovery
- Context preservation between steps

## 🔧 Customization Options

### **Modify Schedules:**
```python
# Change timing in schedule_nba_workflow()
schedule.every().day.at("10:00").do(...)  # 10AM instead of 8AM
```

### **Add More NBA Accounts:**
```python
# In nba_content_discoverer instructions:
"Monitor additional accounts: @wojespn, @ShamsCharania, @ESPN_NBA"
```

### **Adjust Question Types:**
```python
# In nba_question_generator instructions:
"Focus more on betting scenarios and ROI calculations"
```

## 📊 Monitoring & Debugging

### **Enable Detailed Logging:**
```python
nba_workflow = Workflow(
    ...,
    store_events=True,  # Store all workflow events
    stream_intermediate_steps=True  # Real-time step updates
)
```

### **Access Workflow Results:**
```python
response = nba_workflow.run(...)
print(f"Steps completed: {len(response.steps)}")
for step in response.steps:
    print(f"{step.step_name}: {'✅' if step.success else '❌'}")
```

## 🚀 Production Deployment

### **1. Deploy on Server with Agno**
### **2. Set up Environment Variables**  
### **3. Configure Real Twitter & NBA MCP Clients**
### **4. Enable Scheduled Execution**
### **5. Monitor Workflow Logs**

**Your NBA Twitter automation system will then run automatically 6 times daily, creating engaging NBA analytics conversations!** 🏀

## 📈 Expected Results

- **6 NBA analytics interactions per day**
- **Automated discovery of trending NBA content**
- **High-quality, data-driven questions and responses**
- **Seamless integration between @tejsri01 and @BlitzAIBot**
- **Professional, emoji-free formatting**
- **Real NBA statistics and analysis** 