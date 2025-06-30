#!/usr/bin/env python3
"""
Endpoint discovery script for BlitzAgent deployment.
"""

import requests
import json

def discover_endpoints(base_url="https://blitzagent.onrender.com"):
    """Discover available endpoints."""
    print(f"🔍 Discovering endpoints for {base_url}")
    print("=" * 50)
    
    # Test common endpoint patterns
    endpoints_to_test = [
        "/",
        "/health", 
        "/docs",
        "/openapi.json",
        "/v1/",
        "/v1/run",
        "/v1/chat",
        "/v1/agent",
        "/run",
        "/chat",
        "/agent"
    ]
    
    session = requests.Session()
    working_endpoints = []
    
    for endpoint in endpoints_to_test:
        try:
            url = f"{base_url}{endpoint}"
            
            # Try GET first
            response = session.get(url, timeout=10)
            if response.status_code < 400:
                working_endpoints.append((endpoint, "GET", response.status_code))
                print(f"✅ GET  {endpoint:<15} -> {response.status_code}")
            
            # Try POST for API endpoints
            if any(api_path in endpoint for api_path in ['/run', '/chat', '/agent', '/v1']):
                try:
                    post_response = session.post(url, json={"test": "request"}, timeout=10)
                    if post_response.status_code < 500:  # Include 4xx as valid (might just need proper payload)
                        working_endpoints.append((endpoint, "POST", post_response.status_code))
                        print(f"✅ POST {endpoint:<15} -> {post_response.status_code}")
                except:
                    pass
                    
        except Exception as e:
            print(f"❌ {endpoint:<20} -> Error: {str(e)[:30]}...")
    
    print(f"\n📊 Found {len(working_endpoints)} working endpoints")
    
    # Try to get API documentation if available
    try:
        docs_response = session.get(f"{base_url}/docs", timeout=10)
        if docs_response.status_code == 200:
            print(f"\n📚 API Documentation available at: {base_url}/docs")
    except:
        pass
    
    try:
        openapi_response = session.get(f"{base_url}/openapi.json", timeout=10)
        if openapi_response.status_code == 200:
            openapi_data = openapi_response.json()
            print(f"\n🔧 OpenAPI spec available. Found paths:")
            for path in openapi_data.get('paths', {}):
                methods = list(openapi_data['paths'][path].keys())
                print(f"   {path:<20} {methods}")
    except Exception as e:
        print(f"\n⚠️  Could not fetch OpenAPI spec: {e}")

if __name__ == "__main__":
    discover_endpoints() 