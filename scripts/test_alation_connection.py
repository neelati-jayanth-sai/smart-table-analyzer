"""Test Alation API connection with the access token from .env."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    access_token = os.getenv("ALATION_ACCESS_TOKEN")
    refresh_token = os.getenv("ALATION_REFRESH_TOKEN")
    user_id = os.getenv("ALATION_USER_ID")
    base_url = os.getenv("ALATION_BASE_URL")
    verify_ssl = os.getenv("ALATION_VERIFY_SSL", "true").lower() == "true"
    cert_file = os.getenv("ALATION_CERT_FILE")

    if not access_token and not refresh_token:
        print("❌ Neither ALATION_ACCESS_TOKEN nor ALATION_REFRESH_TOKEN found in .env")
        return 1

    if not base_url:
        print("❌ ALATION_BASE_URL not found in .env")
        print("   Add: ALATION_BASE_URL=https://your-alation-instance.alationcloud.com")
        return 1

    import requests
    import urllib3

    # Suppress SSL warnings if verify is disabled
    if not verify_ssl:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Configure SSL verification
    verify = cert_file if cert_file and verify_ssl else verify_ssl

    # If refresh token is available, try to get a fresh access token
    if refresh_token and user_id:
        print("Refreshing access token...")
        try:
            response = requests.post(
                f"{base_url}/integration/v1/createAPIAccessToken/",
                json={"refresh_token": refresh_token, "user_id": user_id},
                timeout=10,
                verify=verify
            )
            if response.status_code == 201:
                access_token = response.json()["api_access_token"]
                print(f"✅ New access token obtained")
            else:
                print(f"⚠️  Token refresh failed: {response.status_code}")
                print(f"   Using existing access token if available")
        except Exception as e:
            print(f"⚠️  Token refresh error: {e}")
            print(f"   Using existing access token if available")

    if not access_token:
        print("❌ No valid access token available")
        return 1

    headers = {"TOKEN": access_token}

    # Test 1: Get data sources
    print(f"Testing connection to {base_url}...")
    print(f"SSL verify: {verify}")
    try:
        response = requests.get(f"{base_url}/integration/v1/datasource/", headers=headers, timeout=10, verify=verify)
        if response.status_code == 200:
            print(f"✅ Connection successful")
            data = response.json()
            # Handle both list and dict response formats
            if isinstance(data, list):
                print(f"   Found {len(data)} data sources")
                for ds in data[:3]:
                    if isinstance(ds, dict):
                        print(f"   - {ds.get('title', ds.get('name', 'N/A'))} (ID: {ds.get('id', 'N/A')})")
                    else:
                        print(f"   - {ds}")
            elif isinstance(data, dict):
                print(f"   Response keys: {list(data.keys())}")
                if "data_sources" in data:
                    print(f"   Found {len(data['data_sources'])} data sources")
                    for ds in data["data_sources"][:3]:
                        print(f"   - {ds.get('title', 'N/A')} (ID: {ds.get('id', 'N/A')})")
            else:
                print(f"   Unexpected response type: {type(data)}")
                print(f"   Response: {str(data)[:200]}")
        else:
            print(f"❌ Connection failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return 1
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return 1

    # Test 2: Try search API to find tables
    print("\nTesting search API for table objects...")
    try:
        # Search for tables using the search API
        search_response = requests.get(
            f"{base_url}/integration/v1/search/",
            headers=headers,
            params={"q": "table", "limit": 5},
            timeout=10,
            verify=verify
        )
        if search_response.status_code == 200:
            print("✅ Search API available")
            result = search_response.json()
            print(f"   Response type: {type(result)}")
            if isinstance(result, dict):
                print(f"   Response keys: {list(result.keys())}")
                if "results" in result:
                    print(f"   Found {len(result['results'])} results")
                    for r in result["results"][:3]:
                        print(f"   - {r.get('title', r.get('name', 'N/A'))} (type: {r.get('otype', 'N/A')})")
            else:
                print(f"   Response: {str(result)[:200]}")
        else:
            print(f"⚠️  Search API returned {search_response.status_code}")
            print(f"   Response: {search_response.text[:200]}")
    except Exception as e:
        print(f"⚠️  Search API test failed: {e}")

    print("\n✅ Alation connection test completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
