#!/usr/bin/env python3
"""
Simple Test - LLM Chat Only

Tests LLM connectivity with a simple message.

Usage:
    python scripts/test_simple.py
"""

import os
import sys
import json
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    pass

try:
    import requests
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("❌ requests library not installed. Run: pip install requests")
    sys.exit(1)


def test_llm():
    """Test LLM with a simple 'Hi' message."""
    print("\n" + "="*80)
    print("  LLM Chat Test - Sending 'Hi' Message")
    print("="*80 + "\n")
    
    client_id = os.getenv("LLM_CLIENT_ID")
    client_secret = os.getenv("LLM_CLIENT_SECRET")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL", "gpt-oss-120b")
    verify_ssl = os.getenv("LLM_VERIFY_SSL", "true").lower() != "false"
    
    print(f"🤖 Model: {model}")
    print(f"🔗 Endpoint: {base_url}")
    print(f"🔒 SSL Verify: {verify_ssl}\n")
    
    # Use client_secret as Bearer token (direct approach)
    headers = {
        "Authorization": f"Bearer {client_secret}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Test message
    test_message = "Hi"
    
    print(f"💬 Sending message: '{test_message}'\n")
    
    # OpenAI-compatible chat format
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": test_message}
        ],
        "temperature": 0.7,
        "max_tokens": 150
    }
    
    # Try different endpoint variations
    endpoints = [
        f"{base_url}/chat/completions",
        f"{base_url.rstrip('/v1')}/v1/chat/completions",
        f"{base_url}/completions"
    ]
    
    for endpoint in endpoints:
        print(f"🔗 Trying: {endpoint}")
        
        try:
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=30,
                verify=verify_ssl
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ Success!\n")
                
                data = response.json()
                
                # Extract message from response
                if "choices" in data:
                    content = data["choices"][0].get("message", {}).get("content", "")
                    if not content:
                        content = data["choices"][0].get("text", "")
                    
                    print("🤖 LLM Response:")
                    print("─" * 80)
                    print(content)
                    print("─" * 80)
                    
                    # Show metadata
                    if "usage" in data:
                        print(f"\n📊 Token Usage:")
                        print(f"   Prompt: {data['usage'].get('prompt_tokens', 'N/A')}")
                        print(f"   Completion: {data['usage'].get('completion_tokens', 'N/A')}")
                        print(f"   Total: {data['usage'].get('total_tokens', 'N/A')}")
                    
                    return True
                else:
                    print(f"\n📄 Full Response:")
                    print(json.dumps(data, indent=2))
                    return True
                    
            elif response.status_code == 404:
                print(f"   ❌ Not found - trying next endpoint...\n")
                continue
                
            else:
                print(f"   ⚠️  Error response:")
                print(f"   {response.text[:300]}\n")
                continue
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:150]}\n")
            continue
    
    print("❌ Could not connect to LLM through any endpoint\n")
    return False


def test_iomete_simple():
    """Test IOMETE with a simple REST API call."""
    print("\n" + "="*80)
    print("  IOMETE Simple Query Test")
    print("="*80 + "\n")
    
    base_url = os.getenv("IOMETE_BASE_URL")
    api_token = os.getenv("IOMETE_API_TOKEN")
    catalog = os.getenv("IOMETE_CATALOG")
    namespace = os.getenv("IOMETE_NAMESPACE")
    verify_ssl = os.getenv("IOMETE_VERIFY_SSL", "true").lower() != "false"
    
    print(f"🔗 IOMETE: {base_url}")
    print(f"📍 Catalog: {catalog}.{namespace}")
    print(f"🔒 SSL Verify: {verify_ssl}\n")
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json"
    }
    
    # Simple test query
    query = "SELECT 1 as test_value, 'Hello from IOMETE' as message"
    
    print(f"📝 Query: {query}\n")
    
    # Try different API paths
    endpoints = [
        f"{base_url}/api/v1/sql-editor/execute",
        f"{base_url}/api/sql/execute",
        f"{base_url}/api/v1/query"
    ]
    
    for endpoint in endpoints:
        print(f"🔗 Trying: {endpoint}")
        
        try:
            payload = {
                "query": query,
                "catalog": catalog,
                "schema": namespace
            }
            
            response = requests.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=30,
                verify=verify_ssl
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                print(f"   ✅ Success!\n")
                data = response.json()
                print(f"📊 Result:")
                print(json.dumps(data, indent=2)[:500])
                return True
                
            elif response.status_code == 404:
                print(f"   ❌ Not found - trying next...\n")
                continue
                
            else:
                print(f"   Response: {response.text[:200]}\n")
                continue
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:150]}\n")
            continue
    
    print("ℹ️  REST API endpoints not found")
    print("   IOMETE may require Spark Connect or JDBC connection\n")
    return False


def main():
    """Run tests."""
    print("\n" + "="*80)
    print("  Quick Test - LLM & IOMETE")
    print("="*80)
    
    # Test LLM
    llm_ok = test_llm()
    
    # Test IOMETE
    iomete_ok = test_iomete_simple()
    
    # Summary
    print("\n" + "="*80)
    print("  Summary")
    print("="*80 + "\n")
    
    if llm_ok:
        print("✅ LLM is working - you can chat with the model!")
    else:
        print("❌ LLM connection failed")
    
    if iomete_ok:
        print("✅ IOMETE REST API is working!")
    else:
        print("ℹ️  IOMETE REST API not accessible (may need Spark Connect)")
    
    if llm_ok:
        print("\n🎉 LLM is ready! You can start using it for analysis.")
        return 0
    else:
        return 1


if __name__ == "__main__":
    sys.exit(main())
