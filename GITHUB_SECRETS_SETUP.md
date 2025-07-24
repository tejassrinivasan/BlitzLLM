# GitHub Secrets Setup Guide

## Step 1: Go to your GitHub repository
1. Open your browser
2. Go to: https://github.com/tejassrinivasan/BlitzLLM
3. Click on "Settings" (top menu bar)
4. Click on "Secrets and variables" → "Actions" (left sidebar)

## Step 2: Add these secrets (click "New repository secret" for each)

### AZURE_OPENAI_API_KEY
- Name: `AZURE_OPENAI_API_KEY`
- Value: `3RxOfsvJrx1vapAtdNJN8tAI5HhSTB2GLq0j3A61MMIOEVaKuo45JQQJ99BCACYeBjFXJ3w3AAABACOGCEvR`

### AZURE_OPENAI_ENDPOINT  
- Name: `AZURE_OPENAI_ENDPOINT`
- Value: `https://blitzgpt.openai.azure.com`

### POSTGRES_HOST
- Name: `POSTGRES_HOST`
- Value: `blitz-instance-1.cdu6kma429k4.us-west-2.rds.amazonaws.com`

### POSTGRES_USER
- Name: `POSTGRES_USER`
- Value: `postgres`

### POSTGRES_PASSWORD
- Name: `POSTGRES_PASSWORD`
- Value: `_V8fn.eo62B(gZD|OcQcu~0|aP8[`

### POSTGRES_DATABASE
- Name: `POSTGRES_DATABASE`
- Value: `nba`

### POSTGRES_PORT
- Name: `POSTGRES_PORT`
- Value: `5432`

### POSTGRES_SSL
- Name: `POSTGRES_SSL`
- Value: `true`

## Step 3: Verify
After adding all 8 secrets, you should see them listed on the Secrets page.

## Step 4: Test the workflow
1. Go to the "Actions" tab in your repo
2. Click on "NBA Production Workflow"
3. Click "Run workflow" → "Run workflow" to test it manually
4. Watch it run and make sure it completes successfully

## Step 5: Check the schedule
Once working, it will automatically run 6 times daily:
- 8:00 AM EST
- 12:00 PM EST  
- 4:00 PM EST
- 8:00 PM EST
- 11:00 PM EST
- 2:00 AM EST

## That's it! 🎉
Your NBA workflow will now run automatically 6 times a day, posting to Twitter! 