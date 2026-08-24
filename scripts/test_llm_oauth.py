#!/usr/bin/env python3
"""
LLM OAuth Test - Dell AIA Gateway

Tests LLM with proper OAuth2 authentication.

Usage:
    python scripts/test_llm_oauth.py
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


def get_oauth_token():
    """Get OAuth2 access token from Dell AIA Gateway."""
    print("\n" + "="*80)
    print("  Step 1: OAuth2 Authentication")
    print("="*80 + "\n")
    
    client_id = os.getenv("LLM_CLIENT_ID")
    client_secret = os.getenv("LLM_CLIENT_SECRET")
    base_url = os.getenv("LLM_BASE_URL")
    verify_ssl = os.getenv("LLM_VERIFY_SSL", "true").lower() != "false"
    
    # Try different token endpoint variations
    token_endpoints = [
        "https://aia.gateway.dell.com/genai/dev/oauth/token",
        "https://aia.gateway.dell.com/genai/dev/v1/oauth/token",
        "https://aia.gateway.dell.com/oauth/token",
        "https://aia.gateway.dell.com/genai/oauth/token",
        f"{base_url}/oauth/token",
        f"{base_url.rstrip('/v1')}/oauth/token"
    ]
    
    print(f"🔑 Client ID: {client_id[:20]}...")
    print(f"🔒 SSL Verify: {verify_ssl}\n")
    
    for token_endpoint in token_endpoints:
        print(f"🔗 Trying token endpoint: {token_endpoint}")
        
        try:
            # OAuth2 client credentials grant
            response = requests.post(
                token_endpoint,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=15,
                verify=verify_ssl
            )
            
            print(f"   Status: {response.status_code}")
            
            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                
                print(f"   ✅ Token obtained successfully!\n")
                print(f"📝 Token Info:")
                print(f"   Type: {token_data.get('token_type', 'unknown')}")
                print(f"   Expires in: {token_data.get('expires_in', 'unknown')} seconds")
                print(f"   Token (first 30 chars): {access_token[:30]}...")
                
                return access_token, token_data
                
            elif response.status_code == 404:
                print(f"   ❌ Not found - trying next...\n")
                continue
                
            else:
                print(f"   ⚠️  Response: {response.text[:300]}\n")
                continue
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:150]}\n")
            continue
    
    print("❌ Could not obtain OAuth token from any endpoint\n")
    return None, None


def test_llm_with_token(access_token):
    """Test LLM chat with OAuth token."""
    print("\n" + "="*80)
    print("  Step 2: Send Message to LLM")
    print("="*80 + "\n")
    
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL", "gpt-oss-120b")
    verify_ssl = os.getenv("LLM_VERIFY_SSL", "true").lower() != "false"
    
    print(f"🤖 Model: {model}")
    print(f"🔗 Endpoint: {base_url}")
    print(f"💬 Message: 'Hi'\n")
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Hi"}
        ],
        "temperature": 0.7,
        "max_tokens": 100
    }
    
    # Try different endpoint paths
    endpoints = [
        f"{base_url}/chat/completions",
        f"{base_url}/v1/chat/completions",
        f"{base_url.rstrip('/v1')}/v1/chat/completions"
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
                
                # Extract response
                if "choices" in data and len(data["choices"]) > 0:
                    message = data["choices"][0].get("message", {}).get("content")
                    if not message:
                        message = data["choices"][0].get("text", "")
                    
                    print("🤖 LLM Response:")
                    print("─" * 80)
                    print(message)
                    print("─" * 80)
                    
                    # Show usage stats
                    if "usage" in data:
                        usage = data["usage"]
                        print(f"\n📊 Token Usage:")
                        print(f"   Prompt tokens: {usage.get('prompt_tokens', 'N/A')}")
                        print(f"   Completion tokens: {usage.get('completion_tokens', 'N/A')}")
                        print(f"   Total tokens: {usage.get('total_tokens', 'N/A')}")
                    
                    # Show model info
                    if "model" in data:
                        print(f"\n🤖 Model used: {data['model']}")
                    
                    return True
                else:
                    print(f"\n📄 Full Response:")
                    print(json.dumps(data, indent=2))
                    return True
                    
            elif response.status_code == 404:
                print(f"   ❌ Not found - trying next...\n")
                continue
                
            elif response.status_code == 401:
                print(f"   ❌ Authentication failed")
                print(f"   Response: {response.text[:200]}\n")
                continue
                
            else:
                print(f"   ⚠️  Response: {response.text[:300]}\n")
                continue
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:150]}\n")
            continue
    
    print("❌ Could not send message through any endpoint\n")
    return False


def main():
    """Run OAuth LLM test."""
    print("\n" + "="*80)
    print("  Dell AIA Gateway - OAuth LLM Test")
    print("="*80)
    
    # Step 1: Get OAuth token
    access_token, token_data = get_oauth_token()
    
    if not access_token:
        print("\n❌ Failed to obtain OAuth token")
        print("\n💡 Check:")
        print("   1. LLM_CLIENT_ID is correct")
        print("   2. LLM_CLIENT_SECRET is correct")
        print("   3. Token endpoint URL")
        print("   4. Network connectivity to Dell AIA Gateway")
        return 1
    
    # Step 2: Test LLM with token
    success = test_llm_with_token(access_token)
    
    # Summary
    print("\n" + "="*80)
    print("  Summary")
    print("="*80 + "\n")
    
    if success:
        print("✅ LLM is fully working!")
        print("   • OAuth authentication: ✓")
        print("   • Chat API: ✓")
        print("   • Message sending: ✓")
        print("\n🎉 You can now use the LLM for analysis!")
        return 0
    else:
        print("⚠️  OAuth token obtained, but chat API failed")
        print("   • Token endpoint: ✓")
        print("   • Chat endpoint: ✗")
        print("\n💡 The token endpoint may need adjustment")
        return 1


if __name__ == "__main__":
    sys.exit(main())
