#!/usr/bin/env python3
"""
Simple test script for BlitzAgent deployment.

Use this to quickly test your deployed agent with different agent IDs and messages.
"""

import requests
import json

def test_agent(base_url="https://blitzagent.onrender.com", agent_id="blitzagent-server", message="Hello!"):
    """Test the deployed BlitzAgent with a simple message."""
    
    print(f"🚀 Testing BlitzAgent at {base_url}")
    print(f"📨 Agent ID: {agent_id}")
    print(f"💬 Message: {message}")
    print("-" * 50)
    
    # Test health first
    try:
        health_response = requests.get(f"{base_url}/health", timeout=10)
        if health_response.status_code == 200:
            print("✅ Service is healthy")
        else:
            print(f"⚠️  Health check warning: {health_response.status_code}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Test agent
    payload = {
        "message": message,
        "user_id": "test_user",
        "session_id": "test_session",
        "agent_id": agent_id
    }
    
    try:
        print(f"\n🤖 Sending request to /v1/runs...")
        response = requests.post(
            f"{base_url}/v1/runs",
            json=payload,
            timeout=30
        )
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("✅ SUCCESS! Agent responded:")
                print(f"📝 Response: {data.get('content', str(data))}")
            except json.JSONDecodeError:
                print("✅ SUCCESS! (Non-JSON response)")
                print(f"📝 Response: {response.text[:200]}...")
        else:
            print("❌ FAILED!")
            try:
                error_data = response.json()
                print(f"🚨 Error: {error_data.get('detail', 'Unknown error')}")
            except json.JSONDecodeError:
                print(f"🚨 Error: {response.text}")
                
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    # Try different agent IDs if one doesn't work
    agent_ids_to_try = [
        "blitzagent-server",  # Our expected ID
        "blitzagent", 
        "BlitzAgent",
        "blitz_single",
        "agent_0",
        "0"
    ]
    
    print("🧪 Simple BlitzAgent Test")
    print("=" * 50)
    
    for agent_id in agent_ids_to_try:
        print(f"\n🔍 Trying agent_id: '{agent_id}'")
        test_agent(agent_id=agent_id, message="What do you do?")
        
        # Check if this one worked by testing again
        try:
            response = requests.post(
                "https://blitzagent.onrender.com/v1/runs",
                json={"message": "test", "agent_id": agent_id},
                timeout=10
            )
            if response.status_code != 400 or "must be provided" not in response.text:
                print(f"🎉 Found working agent_id: '{agent_id}'")
                print("Use this agent_id for future tests!")
                break
        except:
            pass
    
    print(f"\n" + "=" * 50)
    print("💡 If none worked, your deployment might still be updating.")
    print("💡 Check your Render dashboard for deployment status.")
    print("💡 You can also visit https://blitzagent.onrender.com/docs for API documentation.") 