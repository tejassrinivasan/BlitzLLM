#!/usr/bin/env python3
"""
Test script for BlitzAgent deployment.

This script tests the deployed BlitzAgent to ensure it's working correctly
on Render or other deployment platforms.
"""

import requests
import json
import time
import sys
from typing import Dict, Any, Optional


class BlitzAgentTester:
    """Test suite for BlitzAgent deployment."""
    
    def __init__(self, base_url: str = "https://blitzagent.onrender.com"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'BlitzAgent-Test-Client/1.0'
        })
    
    def test_health_check(self) -> bool:
        """Test the health check endpoint."""
        print("🏥 Testing health check...")
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed: {data.get('status', 'unknown')}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    def test_root_endpoint(self) -> bool:
        """Test the root endpoint."""
        print("🏠 Testing root endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Root endpoint passed")
                print(f"   Service: {data.get('service', 'unknown')}")
                print(f"   Status: {data.get('status', 'unknown')}")
                print(f"   Model: {data.get('model', 'unknown')}")
                return True
            else:
                print(f"❌ Root endpoint failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Root endpoint error: {e}")
            return False
    
    def test_agent_simple_query(self) -> bool:
        """Test a simple query to the agent."""
        print("🤖 Testing simple agent query...")
        try:
            payload = {
                "message": "Hello! Can you tell me what you do?",
                "user_id": "test_user_001",
                "session_id": "test_session_001",
                "agent_id": "blitzagent-server"
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/runs",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Simple query passed")
                print(f"   Response: {data.get('content', str(data))[:100]}...")
                return True
            else:
                print(f"❌ Simple query failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False
                
        except Exception as e:
            print(f"❌ Simple query error: {e}")
            return False
    
    def test_agent_sports_query(self) -> bool:
        """Test a sports-related query to the agent."""
        print("⚾ Testing sports analytics query...")
        try:
            payload = {
                "message": "What are the most important baseball statistics to track for player performance?",
                "user_id": "test_user_002",
                "session_id": "test_session_002",
                "agent_id": "blitzagent-server"
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/runs",
                json=payload,
                timeout=45
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✅ Sports query passed")
                print(f"   Response: {data.get('content', str(data))[:150]}...")
                return True
            else:
                print(f"❌ Sports query failed: {response.status_code}")
                print(f"   Response: {response.text[:200]}...")
                return False
                
        except Exception as e:
            print(f"❌ Sports query error: {e}")
            return False
    
    def test_agent_with_streaming(self) -> bool:
        """Test agent with streaming response."""
        print("🌊 Testing streaming response...")
        try:
            payload = {
                "message": "Explain what makes a good baseball pitcher in 2-3 sentences.",
                "user_id": "test_user_003",
                "session_id": "test_session_003",
                "agent_id": "blitzagent-server",
                "stream": True
            }
            
            response = self.session.post(
                f"{self.base_url}/v1/runs",
                json=payload,
                timeout=30,
                stream=True
            )
            
            if response.status_code == 200:
                print("✅ Streaming query initiated")
                
                # Try to read some streaming content
                content_received = False
                for line in response.iter_lines(decode_unicode=True):
                    if line and line.strip():
                        content_received = True
                        print(f"   Streamed: {line[:80]}...")
                        break  # Just test first chunk
                
                if content_received:
                    print("✅ Streaming response received")
                    return True
                else:
                    print("⚠️  Streaming initiated but no content received")
                    return False
            else:
                print(f"❌ Streaming query failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Streaming query error: {e}")
            return False
    
    def test_error_handling(self) -> bool:
        """Test error handling with malformed request."""
        print("🚨 Testing error handling...")
        try:
            # Send malformed request
            response = self.session.post(
                f"{self.base_url}/v1/runs",
                json={"invalid": "request", "agent_id": "blitzagent-server"},
                timeout=10
            )
            
            # We expect this to fail gracefully
            if response.status_code in [400, 422, 500]:
                print("✅ Error handling works (graceful failure)")
                return True
            else:
                print(f"⚠️  Unexpected response to malformed request: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"✅ Error handling works (exception caught): {e}")
            return True
    
    def run_all_tests(self) -> Dict[str, bool]:
        """Run all tests and return results."""
        print(f"🚀 Starting BlitzAgent deployment tests...")
        print(f"🔗 Testing URL: {self.base_url}")
        print("=" * 60)
        
        results = {}
        
        # Basic connectivity tests
        results['health_check'] = self.test_health_check()
        time.sleep(1)
        
        results['root_endpoint'] = self.test_root_endpoint()
        time.sleep(1)
        
        # Agent functionality tests
        results['simple_query'] = self.test_agent_simple_query()
        time.sleep(2)
        
        results['sports_query'] = self.test_agent_sports_query()
        time.sleep(2)
        
        results['streaming'] = self.test_agent_with_streaming()
        time.sleep(1)
        
        results['error_handling'] = self.test_error_handling()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        passed = sum(results.values())
        total = len(results)
        
        for test_name, passed_test in results.items():
            status = "✅ PASSED" if passed_test else "❌ FAILED"
            print(f"{test_name.replace('_', ' ').title():<20} {status}")
        
        print(f"\n🎯 Overall: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Your BlitzAgent deployment is working perfectly!")
        elif passed >= total * 0.8:
            print("✅ Most tests passed! Your deployment is working well.")
        else:
            print("⚠️  Some tests failed. Check your deployment configuration.")
        
        return results


def main():
    """Main function to run tests."""
    # Allow custom URL via command line argument
    base_url = "https://blitzagent.onrender.com"
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    
    print("🧪 BlitzAgent Deployment Test Suite")
    print(f"🔗 Target URL: {base_url}")
    print()
    
    tester = BlitzAgentTester(base_url)
    results = tester.run_all_tests()
    
    # Exit with appropriate code
    if all(results.values()):
        sys.exit(0)  # All tests passed
    else:
        sys.exit(1)  # Some tests failed


if __name__ == "__main__":
    main() 