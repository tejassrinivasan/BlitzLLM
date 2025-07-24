# NBA Workflow Automation Options

Since your MacBook goes to sleep, local cron jobs **won't work**. Here are your alternatives:

## Option 1: GitHub Actions (FREE & Recommended) ⭐

**Pros:** 
- ✅ Completely free
- ✅ Runs in the cloud 24/7
- ✅ No infrastructure needed
- ✅ Easy to manage

**Setup:**
1. Push your code to GitHub (if not already there)
2. Add API keys as GitHub Secrets:
   - Go to your repo → Settings → Secrets and variables → Actions
   - Add these secrets:
     - `AZURE_OPENAI_API_KEY`
     - `AZURE_OPENAI_ENDPOINT` 
     - `POSTGRES_HOST`
     - `POSTGRES_PASSWORD`
3. The workflow file is already created at `.github/workflows/nba-workflow.yml`
4. Push to GitHub and it will run automatically 6x daily

## Option 2: Railway/Render (Paid Cloud)

**Pros:**
- ✅ Professional cloud hosting
- ✅ Easy deployment
- ✅ Great monitoring

**Cost:** ~$5-20/month

**Setup:**
- Deploy as a scheduled job on Railway or Render
- Set environment variables
- Configure cron schedule

## Option 3: AWS Lambda (Serverless)

**Pros:**
- ✅ Pay only for execution time
- ✅ Very cheap (~$1/month)
- ✅ Highly reliable

**Setup:**
- Package as Lambda function
- Use EventBridge for scheduling
- More technical setup required

## Option 4: Raspberry Pi (Local Server)

**Pros:**
- ✅ One-time cost (~$50)
- ✅ Always on, low power
- ✅ Full control

**Setup:**
- Set up Pi with your code
- Run the same cron jobs
- Leave Pi running 24/7

## Option 5: Keep MacBook Awake (Not Recommended)

**Pros:**
- ✅ Uses existing setup

**Cons:**
- ❌ High power consumption
- ❌ Fan noise
- ❌ Wear on laptop

**Command to prevent sleep:**
```bash
sudo pmset -a disablesleep 1  # Disable sleep
sudo pmset -a disablesleep 0  # Re-enable sleep
```

## Recommendation

**Use GitHub Actions** - it's free, reliable, and perfect for this use case. You just need to:

1. Add your API keys as GitHub Secrets
2. Push your code 
3. The workflow will run automatically 6x daily

No laptop needed, no cloud costs, completely automated! 🚀 