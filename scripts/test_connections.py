#!/usr/bin/env python3
"""
Connection Test Script

Tests actual connectivity to IOMETE and LLM endpoints.
Run this after configuring .env to verify credentials work.

Usage:
    python scripts/test_connections.py
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
    print("⚠️  python-dotenv not installed, using environment variables")

try:
    import requests
    # Suppress SSL warnings when verification is disabled
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("❌ requests library not installed")
    print("   Run: pip install requests")
    sys.exit(1)


def test_iomete_connection():
    """Test IOMETE API connection."""
    print("\n" + "="*80)
    print("  IOMETE Connection Test")
    print("="*80 + "\n")
    
    host = os.getenv("IOMETE_HOST")
    user_id = os.getenv("IOMETE_USER_ID")
    api_token = os.getenv("IOMETE_API_TOKEN")
    base_url = os.getenv("IOMETE_BASE_URL", f"https://{host}")
    verify_ssl = os.getenv("IOMETE_VERIFY_SSL", "true").lower() == "true"
    cert_file = os.getenv("IOMETE_CERT_FILE")
    
    print(f"🔗 Endpoint: {base_url}")
    print(f"👤 User: {user_id}")
    print(f"🔒 SSL Verify: {verify_ssl}")
    
    # Prepare SSL verification
    verify = True
    if not verify_ssl:
        verify = False
        print("⚠️  SSL verification disabled")
    elif cert_file and Path(cert_file).exists():
        verify = str(Path(cert_file).absolute())
        print(f"📜 Using certificate: {cert_file}")
    elif cert_file:
        print(f"⚠️  Certificate file not found: {cert_file}")
        print("   Proceeding with system certificates...")
    
    # Test basic connectivity
    try:
        print(f"\n📡 Testing connection to {base_url}...")
        
        # Try to access the base URL
        response = requests.get(
            base_url,
            timeout=10,
            verify=verify,
            allow_redirects=True
        )
        
        print(f"✅ Connection successful (Status: {response.status_code})")
        
        # Try to access API endpoint if available
        api_url = f"{base_url}/api/v1"
        print(f"\n📡 Testing API endpoint: {api_url}...")
        
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            api_url,
            headers=headers,
            timeout=10,
            verify=verify
        )
        
        if response.status_code in [200, 401, 403]:
            if response.status_code == 200:
                print(f"✅ API accessible and authenticated!")
            elif response.status_code == 401:
                print(f"⚠️  Authentication failed (401)")
                print("   Check your IOMETE_API_TOKEN")
            elif response.status_code == 403:
                print(f"⚠️  Access forbidden (403)")
                print("   Token valid but may lack permissions")
        else:
            print(f"ℹ️  API response: {response.status_code}")
        
        return True
        
    except requests.exceptions.SSLError as e:
        print(f"❌ SSL Certificate Error: {e}")
        print("\n💡 Solutions:")
        print("   1. Set IOMETE_VERIFY_SSL=false in .env (testing only)")
        print("   2. Add correct certificate to IOMETE_CERT_FILE")
        return False
        
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Connection Error: {e}")
        print("\n💡 Check:")
        print("   1. Network connectivity")
        print("   2. IOMETE_HOST is correct")
        print("   3. Firewall/proxy settings")
        return False
        
    except requests.exceptions.Timeout:
        print(f"❌ Connection Timeout")
        print("   The server is not responding")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_llm_connection():
    """Test LLM API connection."""
    print("\n" + "="*80)
    print("  LLM Connection Test")
    print("="*80 + "\n")
    
    client_id = os.getenv("LLM_CLIENT_ID")
    client_secret = os.getenv("LLM_CLIENT_SECRET")
    base_url = os.getenv("LLM_BASE_URL")
    token_endpoint = os.getenv("LLM_TOKEN_ENDPOINT")
    provider = os.getenv("LLM_PROVIDER", "custom")
    verify_ssl = os.getenv("LLM_VERIFY_SSL", "true").lower() == "true"
    
    print(f"🤖 Provider: {provider}")
    print(f"🔗 Endpoint: {base_url}")
    print(f"🔑 Client ID: {client_id[:20]}..." if client_id else "❌ Not set")
    print(f"🔒 SSL Verify: {verify_ssl}")
    if not verify_ssl:
        print("⚠️  SSL verification disabled")
    
    if provider == "custom":
        try:
            # Test 1: Basic connectivity
            print(f"\n📡 Testing connection to {base_url}...")
            
            response = requests.get(
                base_url.replace("/v1", "") if "/v1" in base_url else base_url,
                timeout=10,
                allow_redirects=True,
                verify=verify_ssl
            )
            
            print(f"✅ Base URL accessible (Status: {response.status_code})")
            
            # Test 2: Try to get OAuth token
            if token_endpoint:
                print(f"\n🔐 Testing OAuth token endpoint: {token_endpoint}...")
                
                token_response = requests.post(
                    token_endpoint,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": client_id,
                        "client_secret": client_secret
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=10,
                    verify=verify_ssl
                )
                
                if token_response.status_code == 200:
                    print("✅ OAuth token obtained successfully!")
                    token_data = token_response.json()
                    if "access_token" in token_data:
                        print(f"   Token type: {token_data.get('token_type', 'unknown')}")
                        print(f"   Expires in: {token_data.get('expires_in', 'unknown')} seconds")
                        
                        # Test 3: Try to use the token
                        access_token = token_data["access_token"]
                        print(f"\n📡 Testing API with access token...")
                        
                        api_response = requests.get(
                            f"{base_url}/models" if not base_url.endswith("/models") else base_url,
                            headers={"Authorization": f"Bearer {access_token}"},
                            timeout=10,
                            verify=verify_ssl
                        )
                        
                        if api_response.status_code == 200:
                            print("✅ API call successful!")
                            try:
                                data = api_response.json()
                                if "data" in data:
                                    models = data["data"]
                                    print(f"   Available models: {len(models)}")
                                    if models:
                                        print(f"   First model: {models[0].get('id', 'unknown')}")
                            except:
                                pass
                        else:
                            print(f"ℹ️  API response: {api_response.status_code}")
                            print(f"   Response: {api_response.text[:200]}")
                
                else:
                    print(f"❌ OAuth failed (Status: {token_response.status_code})")
                    print(f"   Response: {token_response.text[:200]}")
                    print("\n💡 Check:")
                    print("   1. LLM_CLIENT_ID is correct")
                    print("   2. LLM_CLIENT_SECRET is correct")
                    print("   3. LLM_TOKEN_ENDPOINT is correct")
                    return False
            else:
                # Try direct API call without OAuth
                print(f"\n📡 Testing direct API access...")
                print("   (No LLM_TOKEN_ENDPOINT set, using client credentials)")
                
                headers = {
                    "Authorization": f"Bearer {client_secret}",
                    "Content-Type": "application/json"
                }
                
                api_response = requests.get(
                    f"{base_url}/models",
                    headers=headers,
                    timeout=10,
                    verify=verify_ssl
                )
                
                if api_response.status_code == 200:
                    print("✅ Direct API access successful!")
                else:
                    print(f"ℹ️  API response: {api_response.status_code}")
                    print("   You may need to set LLM_TOKEN_ENDPOINT for OAuth flow")
            
            return True
            
        except requests.exceptions.ConnectionError as e:
            print(f"❌ Connection Error: {e}")
            print("\n💡 Check:")
            print("   1. LLM_BASE_URL is correct")
            print("   2. Network connectivity")
            print("   3. Firewall/proxy settings")
            return False
            
        except requests.exceptions.Timeout:
            print(f"❌ Connection Timeout")
            return False
            
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    else:
        print(f"ℹ️  Provider '{provider}' test not implemented yet")
        print("   This script currently supports 'custom' provider testing")
        return None


def main():
    """Run all connection tests."""
    print("\n" + "="*80)
    print("  Smart Table Analyzer - Connection Tests")
    print("="*80)
    
    # Test IOMETE
    iomete_ok = test_iomete_connection()
    
    # Test LLM
    llm_ok = test_llm_connection()
    
    # Summary
    print("\n" + "="*80)
    print("  Test Summary")
    print("="*80 + "\n")
    
    if iomete_ok:
        print("✅ IOMETE: Connection successful")
    else:
        print("❌ IOMETE: Connection failed")
    
    if llm_ok:
        print("✅ LLM: Connection successful")
    elif llm_ok is None:
        print("⏭️  LLM: Test skipped (provider not supported)")
    else:
        print("❌ LLM: Connection failed")
    
    if iomete_ok and llm_ok:
        print("\n🎉 All connections are working!")
        print("   You're ready to run the analyzer.")
        return 0
    elif iomete_ok or llm_ok:
        print("\n⚠️  Some connections are working, others need attention.")
        return 1
    else:
        print("\n❌ No connections are working. Check configuration.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
