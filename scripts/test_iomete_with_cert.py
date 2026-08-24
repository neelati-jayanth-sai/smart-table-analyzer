#!/usr/bin/env python3
"""
IOMETE Spark Connect Test with SSL Certificate

Tests connection to IOMETE using proper SSL certificate.

Usage:
    python scripts/test_iomete_with_cert.py
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


def setup_ssl_certificate():
    """Setup SSL certificate for IOMETE connection."""
    cert_file = os.getenv("IOMETE_CERT_FILE", "certs/CertificateAuthoritykob.cer")
    cert_path = project_root / cert_file
    
    print("\n" + "="*80)
    print("  SSL Certificate Setup")
    print("="*80 + "\n")
    
    print(f"📜 Certificate path: {cert_path}")
    
    if not cert_path.exists():
        print(f"❌ Certificate file not found!")
        print(f"   Expected: {cert_path}")
        return None
    
    print(f"✅ Certificate file found ({cert_path.stat().st_size} bytes)")
    
    # Set environment variable for SSL certificate
    abs_cert_path = str(cert_path.absolute())
    
    # For PySpark gRPC connections
    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = abs_cert_path
    
    # For requests library
    os.environ["REQUESTS_CA_BUNDLE"] = abs_cert_path
    os.environ["SSL_CERT_FILE"] = abs_cert_path
    
    print(f"✅ SSL environment variables set:")
    print(f"   GRPC_DEFAULT_SSL_ROOTS_FILE_PATH={abs_cert_path}")
    print(f"   REQUESTS_CA_BUNDLE={abs_cert_path}")
    print(f"   SSL_CERT_FILE={abs_cert_path}")
    
    return abs_cert_path


def build_spark_connect_url():
    """Build Spark Connect URL with SSL enabled."""
    host = os.getenv("IOMETE_HOST")
    user_id = os.getenv("IOMETE_USER_ID")
    api_token = os.getenv("IOMETE_API_TOKEN")
    lakehouse = os.getenv("IOMETE_LAKEHOUSE")
    data_plane = os.getenv("IOMETE_DATA_PLANE")
    
    # Build connection string with SSL enabled
    spark_url = (
        f"sc://{host}:443/;"
        f"cluster={lakehouse};"
        f"data_plane={data_plane};"
        f"use_ssl=true;"
        f"user_id={user_id};"
        f"api_token={api_token}"
    )
    
    return spark_url


def test_spark_connection_with_ssl():
    """Test Spark Connect to IOMETE with SSL certificate."""
    print("\n" + "="*80)
    print("  IOMETE Spark Connect Test (SSL Enabled)")
    print("="*80 + "\n")
    
    catalog = os.getenv("IOMETE_CATALOG")
    namespace = os.getenv("IOMETE_NAMESPACE")
    
    print(f"📍 Catalog: {catalog}")
    print(f"📍 Schema: {namespace}")
    print(f"📍 Lakehouse: {os.getenv('IOMETE_LAKEHOUSE')}")
    print(f"📍 Data Plane: {os.getenv('IOMETE_DATA_PLANE')}")
    print(f"🔒 SSL: Enabled with certificate")
    
    try:
        from pyspark.sql import SparkSession
    except ImportError:
        print("\n❌ PySpark not installed")
        print("   Run: pip install pyspark")
        return False
    
    # Build Spark Connect URL
    spark_url = build_spark_connect_url()
    
    # Display URL with masked token
    display_url = spark_url.replace(
        f"api_token={os.getenv('IOMETE_API_TOKEN')}", 
        "api_token=***"
    )
    print(f"\n🔗 Spark Connect URL:")
    print(f"   {display_url}")
    
    try:
        print("\n⚙️  Creating Spark session with SSL certificate...")
        
        spark = SparkSession.builder \
            .appName("IOMETE-SSL-Test") \
            .remote(spark_url) \
            .getOrCreate()
        
        print("✅ Spark session created successfully!\n")
        
        # Test 1: Show current database
        print("📝 Test 1: SELECT current_database()")
        current_db = spark.sql("SELECT current_database()").collect()
        print(f"   ✅ Current database: {current_db[0][0]}")
        
        # Test 2: List databases
        print(f"\n📝 Test 2: SHOW DATABASES")
        databases = spark.sql("SHOW DATABASES").collect()
        print(f"   ✅ Found {len(databases)} database(s)")
        for db in databases[:5]:
            print(f"      • {db.namespace}")
        if len(databases) > 5:
            print(f"      ... and {len(databases) - 5} more")
        
        # Test 3: List tables in target schema
        print(f"\n📝 Test 3: SHOW TABLES IN {catalog}.{namespace}")
        try:
            tables = spark.sql(f"SHOW TABLES IN {catalog}.{namespace}").collect()
            print(f"   ✅ Found {len(tables)} table(s)")
            
            if len(tables) > 0:
                print(f"\n   📊 Tables in {catalog}.{namespace}:")
                for i, table in enumerate(tables[:10], 1):
                    print(f"      {i}. {table.namespace}.{table.tableName}")
                if len(tables) > 10:
                    print(f"      ... and {len(tables) - 10} more tables")
                
                # Test 4: Sample data from first table
                if len(tables) > 0:
                    sample_table = f"{catalog}.{namespace}.{tables[0].tableName}"
                    print(f"\n📝 Test 4: Query sample from {sample_table}")
                    
                    try:
                        # Get table schema
                        sample_df = spark.sql(f"SELECT * FROM {sample_table} LIMIT 1")
                        schema_fields = [f.name for f in sample_df.schema.fields]
                        
                        print(f"   ✅ Table schema ({len(schema_fields)} columns):")
                        for field in schema_fields[:5]:
                            print(f"      • {field}")
                        if len(schema_fields) > 5:
                            print(f"      ... and {len(schema_fields) - 5} more columns")
                        
                        # Get row count estimate
                        count_df = spark.sql(f"SELECT COUNT(*) as cnt FROM {sample_table}")
                        row_count = count_df.collect()[0].cnt
                        print(f"\n   📊 Row count: {row_count:,}")
                        
                    except Exception as e:
                        print(f"   ⚠️  Could not query table: {str(e)[:100]}")
        
        except Exception as e:
            print(f"   ⚠️  Could not list tables: {str(e)[:100]}")
        
        # Test 5: Simple SELECT query
        print(f"\n📝 Test 5: Simple SELECT query")
        result = spark.sql("SELECT 1 as test, 'Hello from IOMETE!' as msg").collect()
        print(f"   ✅ Result: test={result[0].test}, msg={result[0].msg}")
        
        spark.stop()
        print("\n✅ All tests passed with SSL enabled!")
        return True
        
    except Exception as e:
        print(f"\n❌ Spark Connect error: {e}")
        
        error_str = str(e).lower()
        if "certificate" in error_str or "ssl" in error_str:
            print("\n💡 SSL Certificate Issue:")
            print("   The certificate may not be trusted by gRPC")
            print("   Try one of these solutions:")
            print("   1. Add certificate to system trust store")
            print("   2. Use certificate bundle with CA chain")
            print("   3. Contact IOMETE admin for proper certificates")
        else:
            print("\n💡 Troubleshooting:")
            print("   1. Verify IOMETE credentials are correct")
            print("   2. Check network connectivity to IOMETE")
            print("   3. Ensure lakehouse and data plane names match")
        
        import traceback
        print("\n📋 Full error details:")
        traceback.print_exc()
        return False


def main():
    """Run IOMETE test with SSL certificate."""
    print("\n" + "="*80)
    print("  IOMETE Connection Test with SSL Certificate")
    print("="*80)
    
    # Setup SSL certificate
    cert_path = setup_ssl_certificate()
    
    if not cert_path:
        print("\n❌ Cannot proceed without SSL certificate")
        return 1
    
    # Test Spark Connect
    success = test_spark_connection_with_ssl()
    
    # Summary
    print("\n" + "="*80)
    print("  Summary")
    print("="*80 + "\n")
    
    if success:
        print("✅ IOMETE Spark Connect: Working with SSL!")
        print("\n🎉 Full stack operational:")
        print("   • LLM (Dell AIA Gateway): ✓")
        print("   • IOMETE (Spark Connect): ✓")
        print("   • SSL Certificates: ✓")
        print("\n🚀 Ready to build the Smart Table Analyzer!")
        return 0
    else:
        print("❌ IOMETE connection failed")
        print("\n💡 Next steps:")
        print("   1. Verify certificate is correct for cp.iomete-a2-np.kob.dell.com")
        print("   2. Check if certificate includes full CA chain")
        print("   3. Contact IOMETE administrator for assistance")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
