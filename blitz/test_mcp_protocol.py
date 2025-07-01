#!/usr/bin/env python3
import asyncio
import json
import subprocess
import sys
from pathlib import Path

async def test_mcp_protocol():
    """Test proper MCP protocol with initialization"""
    mcp_path = Path(__file__).parent.parent / "mcp"
    start_script = str(mcp_path / "start.sh")
    
    # Start the MCP server process
    proc = await asyncio.create_subprocess_exec(
        "bash", start_script, "--transport", "stdio",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    async def send_request(request):
        """Send a JSON-RPC request"""
        json_str = json.dumps(request) + "\n"
        proc.stdin.write(json_str.encode())
        await proc.stdin.drain()
        
        # Read response
        response_line = await proc.stdout.readline()
        if response_line:
            return json.loads(response_line.decode().strip())
        return None
    
    try:
        # Step 1: Initialize the MCP server
        print("1. Sending initialization request...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "clientInfo": {
                    "name": "BlitzAgent Test",
                    "version": "1.0.0"
                }
            }
        }
        
        init_response = await send_request(init_request)
        print(f"Init response: {init_response}")
        
        # Step 2: Send initialized notification
        print("2. Sending initialized notification...")
        initialized_request = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized"
        }
        
        await send_request(initialized_request)
        
        # Step 3: List tools
        print("3. Listing available tools...")
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        tools_response = await send_request(tools_request)
        print(f"Tools response: {tools_response}")
        
        if tools_response and "result" in tools_response:
            tools = tools_response["result"].get("tools", [])
            print(f"Available tools: {[tool['name'] for tool in tools]}")
            
            # Step 4: Test calling a tool
            if tools:
                tool_name = "get_database_documentation"
                if any(tool["name"] == tool_name for tool in tools):
                    print(f"4. Testing tool call: {tool_name}")
                    tool_request = {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {
                            "name": tool_name,
                            "arguments": {"league": "mlb"}
                        }
                    }
                    
                    tool_response = await send_request(tool_request)
                    print(f"Tool response: {tool_response}")
                    
                    if tool_response and not tool_response.get("error"):
                        print("✅ Tool call successful!")
                        return True
                    else:
                        print("❌ Tool call failed")
                        return False
    
    except Exception as e:
        print(f"❌ Error during MCP protocol test: {e}")
        return False
    
    finally:
        # Clean up
        proc.terminate()
        await proc.wait()
    
    return False

if __name__ == "__main__":
    success = asyncio.run(test_mcp_protocol())
    print(f"Test {'PASSED' if success else 'FAILED'}")
