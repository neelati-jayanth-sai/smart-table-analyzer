#!/usr/bin/env python3
"""
IOMETE Spark Connect Test

Tests connection to IOMETE using Spark Connect protocol.

Usage:
    python scripts/test_iomete_spark.py
"""

import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / '.env', override=True)


def build_spark_connect_url(use_ssl=False):
    """Build Spark Connect URL from environment variables."""
    host = os.getenv("IOMETE_HOST")
    user_id = os.getenv("IOMETE_USER_ID")
    api_token = os.getenv("IOMETE_API_TOKEN")
    lakehouse = os.getenv("IOMETE_LAKEHOUSE")
    data_plane = os.getenv("IOMETE_DATA_PLANE")
    
    # Build connection string
    # Note: use_ssl=false for now due to certificate issues
    spark_url = (
        f"sc://{host}:443/;"
        f"cluster={lakehouse};"
        f"data_plane={data_plane};"
        f"use_ssl={'true' if use_ssl else 'false'};"
        f"user_id={user_id};"
        f"api_token={api_token}"
    )
    
    return spark_url


def test_spark_connection():
    """Test Spark Connect to IOMETE."""
    print("\n" + "="*80)
    print("  IOMETE Spark Connect Test")
    print("="*80 + "\n")
    
    catalog = os.getenv("IOMETE_CATALOG")
    namespace = os.getenv("IOMETE_NAMESPACE")
    
    print(f"📍 Catalog: {catalog}")
    print(f"📍 Schema: {namespace}")
    print(f"📍 Lakehouse: {os.getenv('IOMETE_LAKEHOUSE')}")
    print(f"📍 Data Plane: {os.getenv('IOMETE_DATA_PLANE')}")
    
    try:
        from pyspark.sql import SparkSession
    except ImportError:
        print("\n❌ PySpark not installed")
        print("   Run: pip install pyspark")
        return False
    
    # Build Spark Connect URL (SSL disabled for now due to cert issues)
    spark_url = build_spark_connect_url(use_ssl=False)
    
    # Display URL with masked token
    display_url = spark_url.replace(
        f"api_token={os.getenv('IOMETE_API_TOKEN')}", 
        "api_token=***"
    )
    print(f"\n🔗 Spark Connect URL:")
    print(f"   {display_url}")
    print(f"   ⚠️  SSL verification disabled (use_ssl=false)")
    
    try:
        print("\n⚙️  Creating Spark session...")
        
        spark = SparkSession.builder \
            .appName("IOMETE-Test") \
            .remote(spark_url) \
            .getOrCreate()
        
        print("✅ Spark session created successfully!\n")
        
        # Test 1: Show current database
        print("📝 Test 1: SHOW CURRENT DATABASE")
        current_db = spark.sql("SELECT current_database()").collect()
        print(f"   Current database: {current_db[0][0]}")
        
        # Test 2: List databases
        print(f"\n📝 Test 2: SHOW DATABASES")
        databases = spark.sql("SHOW DATABASES").collect()
        print(f"   Found {len(databases)} database(s):")
        for db in databases[:10]:  # Show first 10
            print(f"   • {db.namespace}")
        
        # Test 3: List tables in target schema
        print(f"\n📝 Test 3: SHOW TABLES IN {catalog}.{namespace}")
        try:
            tables = spark.sql(f"SHOW TABLES IN {catalog}.{namespace}").collect()
            print(f"   Found {len(tables)} table(s):")
            for table in tables[:20]:  # Show first 20
                print(f"   • {table.namespace}.{table.tableName}")
            
            # Test 4: Query a sample table if available
            if len(tables) > 0:
                sample_table = f"{catalog}.{namespace}.{tables[0].tableName}"
                print(f"\n📝 Test 4: Sample query from {sample_table}")
                
                sample_df = spark.sql(f"SELECT * FROM {sample_table} LIMIT 5")
                print(f"   Schema: {sample_df.schema}")
                print(f"   Row count (sample): {sample_df.count()}")
                
                rows = sample_df.collect()
                if rows:
                    print(f"\n   Sample data (first row):")
                    for field in sample_df.schema.fields:
                        print(f"   • {field.name}: {rows[0][field.name]}")
        
        except Exception as e:
            print(f"   ⚠️  Could not list tables: {e}")
        
        # Test 5: Simple SELECT query
        print(f"\n📝 Test 5: Simple SELECT query")
        result = spark.sql("SELECT 1 as test_value, 'Hello from IOMETE' as message").collect()
        print(f"   Result: test_value={result[0].test_value}, message={result[0].message}")
        
        spark.stop()
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Spark Connect error: {e}")
        print("\n💡 Troubleshooting:")
        print("   1. Verify IOMETE credentials are correct")
        print("   2. Check network connectivity to IOMETE")
        print("   3. Ensure lakehouse and data plane names are correct")
        print("   4. Verify SSL certificates if use_ssl=true")
        
        import traceback
        traceback.print_exc()
        return False


def test_with_llm_integration():
    """Test using both IOMETE and LLM together."""
    print("\n" + "="*80)
    print("  Integration Test: IOMETE + LLM")
    print("="*80 + "\n")
    
    try:
        from pyspark.sql import SparkSession
        import httpx
        import authentication_provider
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False
    
    # Setup Spark
    spark_url = build_spark_connect_url(use_ssl=False)
    catalog = os.getenv("IOMETE_CATALOG")
    namespace = os.getenv("IOMETE_NAMESPACE")
    
    # Setup LLM
    base_url = os.getenv("LLM_BASE_URL")
    model = os.getenv("LLM_MODEL", "gpt-oss-120b")
    
    try:
        print("⚙️  Setting up Spark session...")
        spark = SparkSession.builder \
            .appName("IOMETE-LLM-Integration") \
            .remote(spark_url) \
            .getOrCreate()
        
        print("✅ Spark connected\n")
        
        # Get table list
        print(f"📊 Fetching table list from {catalog}.{namespace}...")
        tables = spark.sql(f"SHOW TABLES IN {catalog}.{namespace}").collect()
        table_names = [f"{t.namespace}.{t.tableName}" for t in tables[:5]]
        
        print(f"   Found {len(tables)} tables")
        print(f"   Sample: {table_names[:3]}")
        
        # Ask LLM about the tables
        print("\n🤖 Asking LLM to analyze table names...\n")
        
        # Setup LLM client
        use_sso = os.getenv("USE_SSO", "false").lower() == "true"
        server_side_refresh = os.getenv("ENABLE_TOKEN_REFRESH_AT_SERVER_SIDE", "true").lower() == "true"
        
        if use_sso:
            client = httpx.Client(verify=False)
        elif server_side_refresh:
            client = httpx.Client(verify=False)
        else:
            auth = authentication_provider.AuthenticationProviderWithClientSideTokenRefresh()
            client = httpx.Client(auth=auth, verify=False)
        
        # Get headers
        import uuid
        auth_provider = authentication_provider.AuthenticationProvider()
        
        headers = {
            "x-correlation-id": str(uuid.uuid4()),
            'accept': '*/*',
            'Content-Type': 'application/json'
        }
        
        if use_sso:
            headers['Authorization'] = 'Bearer ' + auth_provider.generate_auth_token()
        elif server_side_refresh:
            headers['Authorization'] = 'Basic ' + auth_provider.get_basic_credentials()
        
        # Ask LLM
        prompt = f"I have these Iceberg tables in my data lakehouse: {', '.join(table_names[:5])}. Based on the table names, what might this data be used for? Keep the response brief (2-3 sentences)."
        
        response = client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 150
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            data = response.json()
            llm_response = data["choices"][0]["message"]["content"]
            
            print("🤖 LLM Analysis:")
            print("─" * 80)
            print(llm_response)
            print("─" * 80)
            
            print("\n✅ Integration test successful!")
            print("   • IOMETE: Connected and queried")
            print("   • LLM: Analyzed table data")
            print("   • Both systems working together!")
            
            spark.stop()
            client.close()
            return True
        else:
            print(f"❌ LLM request failed: {response.status_code}")
            print(f"   {response.text}")
            spark.stop()
            client.close()
            return False
            
    except Exception as e:
        print(f"❌ Integration test error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all IOMETE tests."""
    print("\n" + "="*80)
    print("  IOMETE Connection & Integration Tests")
    print("="*80)
    
    # Test 1: Basic Spark Connect
    spark_ok = test_spark_connection()
    
    # Test 2: Integration with LLM
    if spark_ok:
        integration_ok = test_with_llm_integration()
    else:
        integration_ok = False
        print("\n⏭️  Skipping integration test (Spark connection failed)")
    
    # Summary
    print("\n" + "="*80)
    print("  Summary")
    print("="*80 + "\n")
    
    if spark_ok:
        print("✅ IOMETE Spark Connect: Working")
    else:
        print("❌ IOMETE Spark Connect: Failed")
    
    if integration_ok:
        print("✅ IOMETE + LLM Integration: Working")
    elif not spark_ok:
        print("⏭️  IOMETE + LLM Integration: Skipped")
    else:
        print("❌ IOMETE + LLM Integration: Failed")
    
    if spark_ok and integration_ok:
        print("\n🎉 All systems operational!")
        print("   You can now build the Smart Table Analyzer!")
        return 0
    elif spark_ok:
        print("\n⚠️  IOMETE works, but integration needs attention")
        return 1
    else:
        print("\n❌ IOMETE connection needs to be fixed first")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
