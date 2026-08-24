#!/usr/bin/env python3
"""
Live Query Test Script

Tests actual queries to IOMETE and LLM interactions.
Validates end-to-end connectivity with real data.

Usage:
    python scripts/test_live_query.py
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

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
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("❌ requests library not installed")
    print("   Run: pip install requests")
    sys.exit(1)


def print_header(title: str) -> None:
    """Print formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def test_iomete_query():
    """Test querying IOMETE with a simple SQL query."""
    print_header("IOMETE Query Test")
    
    host = os.getenv("IOMETE_HOST")
    user_id = os.getenv("IOMETE_USER_ID")
    api_token = os.getenv("IOMETE_API_TOKEN")
    base_url = os.getenv("IOMETE_BASE_URL", f"https://{host}")
    catalog = os.getenv("IOMETE_CATALOG")
    namespace = os.getenv("IOMETE_NAMESPACE")
    data_plane = os.getenv("IOMETE_DATA_PLANE")
    lakehouse = os.getenv("IOMETE_LAKEHOUSE")
    verify_ssl = os.getenv("IOMETE_VERIFY_SSL", "true").lower() != "false"
    
    print(f"📍 Catalog: {catalog}")
    print(f"📍 Namespace: {namespace}")
    print(f"📍 Data Plane: {data_plane}")
    print(f"📍 Lakehouse: {lakehouse}")
    
    # Try different API endpoints
    queries_to_test = [
        f"SHOW TABLES IN {catalog}.{namespace}",
        f"SHOW DATABASES",
        f"SELECT 1 as test_value, 'Hello from IOMETE' as message"
    ]
    
    # Possible API endpoints for IOMETE
    api_endpoints = [
        f"{base_url}/api/v1/sql-editor/execute",
        f"{base_url}/api/v1/query",
        f"{base_url}/lakehouse/{lakehouse}/sql",
        f"{base_url}/data-plane/{data_plane}/query"
    ]
    
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    success = False
    
    for query in queries_to_test:
        print(f"\n📝 Testing query: {query}")
        
        for endpoint in api_endpoints:
            try:
                print(f"   🔗 Trying endpoint: {endpoint}")
                
                payload = {
                    "query": query,
                    "catalog": catalog,
                    "schema": namespace,
                    "data_plane": data_plane,
                    "lakehouse": lakehouse
                }
                
                response = requests.post(
                    endpoint,
                    headers=headers,
                    json=payload,
                    timeout=30,
                    verify=verify_ssl
                )
                
                print(f"      Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"      ✅ Success!")
                    try:
                        data = response.json()
                        print(f"      📊 Response: {json.dumps(data, indent=2)[:500]}...")
                        success = True
                        return True
                    except:
                        print(f"      📄 Response text: {response.text[:200]}")
                    break
                elif response.status_code == 404:
                    print(f"      ❌ Endpoint not found")
                    continue
                else:
                    print(f"      ⚠️  Response: {response.text[:200]}")
                    
            except requests.exceptions.Timeout:
                print(f"      ⏱️  Timeout")
                continue
            except Exception as e:
                print(f"      ❌ Error: {str(e)[:100]}")
                continue
        
        if success:
            break
    
    if not success:
        print("\n❌ Could not execute query through any endpoint")
        print("\n💡 IOMETE API documentation needed to find correct endpoint")
        print("   Common patterns:")
        print("   - REST API endpoint for SQL execution")
        print("   - Spark Connect endpoint (sc://)")
        print("   - JDBC/Thrift endpoint")
        
        # Try to list available endpoints
        print("\n🔍 Attempting to discover API endpoints...")
        try:
            response = requests.get(
                f"{base_url}/api",
                headers=headers,
                timeout=10,
                verify=verify_ssl
            )
            if response.status_code == 200:
                print(f"   API info: {response.text[:500]}")
        except:
            pass
    
    return success


def test_llm_chat():
    """Test sending a message to the LLM."""
    print_header("LLM Chat Test")
    
    client_id = os.getenv("LLM_CLIENT_ID")
    client_secret = os.getenv("LLM_CLIENT_SECRET")
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL", "gpt-oss-120b")
    token_endpoint = os.getenv("LLM_TOKEN_ENDPOINT")
    verify_ssl = os.getenv("LLM_VERIFY_SSL", "true").lower() != "false"
    
    print(f"🤖 Model: {model}")
    print(f"🔗 Endpoint: {base_url}")
    
    try:
        # Get access token if OAuth is configured
        access_token = None
        
        if token_endpoint:
            print(f"\n🔐 Getting OAuth token from {token_endpoint}...")
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
                token_data = token_response.json()
                access_token = token_data.get("access_token")
                print(f"   ✅ Token obtained")
            else:
                print(f"   ❌ Token request failed: {token_response.status_code}")
                print(f"   Response: {token_response.text[:200]}")
        
        # Prepare authorization
        if access_token:
            auth_header = f"Bearer {access_token}"
        else:
            # Try using client_secret directly as token
            auth_header = f"Bearer {client_secret}"
        
        # Test message
        test_message = "Hi! This is a test message. Please respond with a simple greeting."
        
        print(f"\n💬 Sending test message: '{test_message}'")
        
        # Try OpenAI-compatible chat completion format
        chat_payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": test_message}
            ],
            "temperature": 0.7,
            "max_tokens": 100
        }
        
        endpoints_to_try = [
            f"{base_url}/chat/completions",
            f"{base_url}/completions",
            f"{base_url}/generate",
            base_url
        ]
        
        success = False
        
        for endpoint in endpoints_to_try:
            print(f"\n🔗 Trying endpoint: {endpoint}")
            
            try:
                response = requests.post(
                    endpoint,
                    headers={
                        "Authorization": auth_header,
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    json=chat_payload,
                    timeout=30,
                    verify=verify_ssl
                )
                
                print(f"   Status: {response.status_code}")
                
                if response.status_code == 200:
                    print(f"   ✅ Success!")
                    
                    try:
                        data = response.json()
                        
                        # Parse OpenAI-style response
                        if "choices" in data and len(data["choices"]) > 0:
                            message = data["choices"][0].get("message", {}).get("content")
                            if not message:
                                message = data["choices"][0].get("text")
                            
                            print(f"\n🤖 LLM Response:")
                            print(f"{'─' * 80}")
                            print(f"{message}")
                            print(f"{'─' * 80}")
                            
                            print(f"\n📊 Full response structure:")
                            print(json.dumps(data, indent=2)[:500])
                            
                            success = True
                            return True
                        else:
                            print(f"   📄 Response: {json.dumps(data, indent=2)[:500]}")
                            
                    except json.JSONDecodeError:
                        print(f"   📄 Response text: {response.text[:500]}")
                    
                    success = True
                    break
                    
                elif response.status_code == 404:
                    print(f"   ❌ Endpoint not found")
                    continue
                    
                elif response.status_code == 401:
                    print(f"   ❌ Authentication failed")
                    print(f"   Response: {response.text[:200]}")
                    continue
                    
                else:
                    print(f"   ⚠️  Status {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
                    continue
                    
            except requests.exceptions.Timeout:
                print(f"   ⏱️  Request timeout")
                continue
            except Exception as e:
                print(f"   ❌ Error: {str(e)[:200]}")
                continue
        
        if not success:
            print("\n❌ Could not send message through any endpoint")
            print("\n💡 Check LLM API documentation for:")
            print("   - Correct endpoint path (e.g., /v1/chat/completions)")
            print("   - Authentication method (OAuth vs API key)")
            print("   - Request/response format")
        
        return success
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_spark_connect():
    """Test Spark Connect connection to IOMETE."""
    print_header("IOMETE Spark Connect Test")
    
    host = os.getenv("IOMETE_HOST")
    user_id = os.getenv("IOMETE_USER_ID")
    api_token = os.getenv("IOMETE_API_TOKEN")
    data_plane = os.getenv("IOMETE_DATA_PLANE")
    lakehouse = os.getenv("IOMETE_LAKEHOUSE")
    catalog = os.getenv("IOMETE_CATALOG")
    namespace = os.getenv("IOMETE_NAMESPACE")
    
    # Construct Spark Connect URL
    spark_url = f"sc://{host}:443/;token={api_token};use_ssl=true"
    
    print(f"🔗 Spark Connect URL: sc://{host}:443/;token=***;use_ssl=true")
    print(f"📍 Target: {catalog}.{namespace}")
    
    try:
        from pyspark.sql import SparkSession
        
        print("\n⚙️  Creating Spark session...")
        
        spark = SparkSession.builder \
            .appName("IOMETE-Test") \
            .remote(spark_url) \
            .getOrCreate()
        
        print("✅ Spark session created!")
        
        # Test simple query
        print(f"\n📝 Running test query: SHOW TABLES IN {catalog}.{namespace}")
        
        df = spark.sql(f"SHOW TABLES IN {catalog}.{namespace}")
        tables = df.collect()
        
        print(f"\n📊 Found {len(tables)} tables:")
        for row in tables[:10]:  # Show first 10
            print(f"   • {row}")
        
        spark.stop()
        return True
        
    except ImportError:
        print("⚠️  PySpark not installed")
        print("   Run: pip install pyspark")
        print("   This is optional - REST API can work without PySpark")
        return None
        
    except Exception as e:
        print(f"❌ Spark Connect error: {e}")
        print("\n💡 Spark Connect may require:")
        print("   - Correct host and port")
        print("   - Valid authentication token")
        print("   - Network access to Spark endpoint")
        return False


def main():
    """Run all live tests."""
    print("\n" + "="*80)
    print("  Smart Table Analyzer - Live Query & LLM Test")
    print("="*80)
    print(f"\n⏰ Test Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test LLM first (simpler, faster)
    llm_ok = test_llm_chat()
    
    # Test IOMETE query
    iomete_ok = test_iomete_query()
    
    # Test Spark Connect (optional)
    spark_ok = test_spark_connect()
    
    # Summary
    print_header("Test Summary")
    
    if llm_ok:
        print("✅ LLM: Successfully sent and received messages")
    else:
        print("❌ LLM: Could not communicate with LLM endpoint")
    
    if iomete_ok:
        print("✅ IOMETE: Successfully executed SQL queries")
    elif spark_ok:
        print("✅ IOMETE: Spark Connect working (REST API needs investigation)")
    else:
        print("❌ IOMETE: Could not execute queries (endpoint discovery needed)")
    
    if spark_ok:
        print("✅ Spark Connect: Working")
    elif spark_ok is None:
        print("⏭️  Spark Connect: Skipped (PySpark not installed)")
    else:
        print("❌ Spark Connect: Failed")
    
    print("\n" + "─"*80)
    
    if llm_ok and (iomete_ok or spark_ok):
        print("\n🎉 Core functionality is working!")
        print("   You can start using the Smart Table Analyzer.")
        return 0
    elif llm_ok or iomete_ok or spark_ok:
        print("\n⚠️  Partial success - some components working.")
        print("   Review errors above and check documentation.")
        return 1
    else:
        print("\n❌ Tests failed - see details above.")
        print("\n💡 Next steps:")
        print("   1. Check IOMETE API documentation for correct endpoints")
        print("   2. Verify LLM API format matches your provider")
        print("   3. Contact your IOMETE/LLM administrator if needed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
