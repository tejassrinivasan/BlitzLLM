# Cofounder Setup Guide - Blitz Agent MCP

Quick setup guide to get the Blitz Agent MCP server running in Cursor.

## Step 1: Add to Cursor MCP Config

Add this to your `~/.cursor/mcp.json` file:

```json
{
  "mcpServers": {
    "blitz-agent-uvx": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/tejassrinivasan/BlitzLLM.git#subdirectory=mcp", "blitz-agent-mcp"]
    }
  }
}
```

## Step 2: Get Config File 

You need to copy the config file from our repo. Choose one option:

### Option A: Download from GitHub (easiest)
1. Go to https://github.com/tejassrinivasan/BlitzLLM/blob/main/mcp/config.json
2. Click "Raw" button
3. Copy all the content
4. Create the config directory and file:
```bash
mkdir -p ~/.config/blitz-agent-mcp
# Then paste the content into this file:
nano ~/.config/blitz-agent-mcp/config.json
```

### Option B: Clone the repo locally
```bash
# Clone the repo
git clone https://github.com/tejassrinivasan/BlitzLLM.git
cd BlitzLLM

# Copy the config 
mkdir -p ~/.config/blitz-agent-mcp
cp mcp/config.json ~/.config/blitz-agent-mcp/config.json
```

## Step 3: Restart Cursor

After making these changes, restart Cursor for the MCP server to load.

## Step 4: Verify Setup

You should see `blitz-agent-uvx` appear in Cursor's MCP tools. You can test it by asking Cursor to query some MLB data.

## Troubleshooting

If you get errors:
1. Make sure you have `uvx` installed: `pip install uv`
2. Verify you have access to the private GitHub repo
3. Check that the config file is in the right location: `~/.config/blitz-agent-mcp/config.json`
4. Try restarting Cursor

## What This Gives You

Once set up, you'll have access to all these tools:
- ✅ MLB/NBA database queries
- ✅ AI-powered query generation  
- ✅ Data visualization and charts
- ✅ Web scraping capabilities
- ✅ Linear regression analysis
- ✅ Query validation and optimization

## Need Help?

Ask Tejas for:
- Access to the private GitHub repository if needed
- Help troubleshooting any setup issues 