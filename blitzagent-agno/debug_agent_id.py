#!/usr/bin/env python3
"""
Debug script to find the correct agent_id for the deployed BlitzAgent.
"""

import requests
import json
import time

def test_agent_id(agent_id, message="test"):
    """Test a specific agent_id."""
    try:
        response = requests.post(
            "https://blitzagent.onrender.com/v1/runs",
            json={
                "message": message,
                "agent_id": agent_id,
                "user_id": "debug_user",
                "session_id": "debug_session"
            },
            timeout=15
        )
        
        if response.status_code == 200:
            return True, "SUCCESS", response.json()
        elif response.status_code == 400 and "must be provided" in response.text:
            return False, "ID_NOT_FOUND", response.json()
        else:
            return False, f"HTTP_{response.status_code}", response.text[:100]
            
    except Exception as e:
        return False, "ERROR", str(e)

def main():
    print("🔍 Debug: Finding the correct agent_id")
    print("=" * 60)
    
    # Test various possible agent_id patterns
    patterns_to_test = [
        # Our expected
        "blitzagent-server",
        
        # Based on agent name variations
        "BlitzAgent Server",
        "blitzagent_server", 
        "BlitzAgent_Server",
        "blitzagent server",
        
        # Based on app_id from FastAPIApp
        "blitzagent",
        "BlitzAgent",
        
        # Default patterns
        "agent",
        "default",
        "main",
        "primary",
        
        # Numeric patterns
        "0", "1", "2",
        "agent_0", "agent_1", "agent_2",
        
        # Hash-like patterns (maybe Agno generates these)
        "agent-0", "agent-1", "agent-2",
        
        # UUID-like first parts (in case it's generated)
        "00000000-0000-0000-0000-000000000000",
        
        # Based on the app structure
        "blitzagent/agent",
        "blitzagent:agent",
        "v1/agent",
    ]
    
    print(f"Testing {len(patterns_to_test)} possible agent_id patterns...\n")
    
    working_ids = []
    
    for i, agent_id in enumerate(patterns_to_test):
        print(f"{i+1:2d}. Testing: '{agent_id}'", end=" ... ")
        
        success, status, result = test_agent_id(agent_id)
        
        if success:
            print("✅ WORKS!")
            working_ids.append(agent_id)
            print(f"    Response: {str(result)[:100]}...")
        elif status == "ID_NOT_FOUND":
            print("❌ ID not found")
        else:
            print(f"❌ {status}")
            if len(str(result)) < 150:
                print(f"    Detail: {result}")
        
        # Small delay to be nice to the server
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    if working_ids:
        print(f"🎉 Found {len(working_ids)} working agent_id(s):")
        for agent_id in working_ids:
            print(f"   ✅ '{agent_id}'")
        print("\nUse any of these in your API calls!")
    else:
        print("❌ No working agent_id found.")
        print("\nPossible issues:")
        print("1. Agent might not be registered properly in FastAPIApp")
        print("2. Agent_id might be dynamically generated")
        print("3. The API might require a different authentication method")
        print("4. There might be a bug in the agent registration")
        
        print("\n💡 Suggestions:")
        print("1. Check Render logs for any agent registration messages")
        print("2. Try visiting https://blitzagent.onrender.com/docs for more info")
        print("3. Check if the agent is created with a different ID than expected")

if __name__ == "__main__":
    main() 