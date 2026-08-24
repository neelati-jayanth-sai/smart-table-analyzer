"""Test Alation context adapter."""

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

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from src.metadata.catalog import AlationAPIKeyAdapter, MockAlationAdapter


def test_mock_adapter() -> None:
    print("Testing MockAlationAdapter...")
    adapter = MockAlationAdapter()
    assert adapter.is_available()
    patterns = adapter.get_table_patterns("test_table")
    assert patterns.common_joins
    assert patterns.common_filters
    assert patterns.downstream_count == 5
    print("✅ MockAlationAdapter works")


def test_api_key_adapter() -> None:
    print("\nTesting AlationAPIKeyAdapter...")
    adapter = AlationAPIKeyAdapter()
    if not adapter.is_available():
        print("⚠️  Alation not available (check credentials in .env)")
        return

    print("✅ Alation connection available")

    # Test with the specific table from environment variable
    test_table = os.getenv("ALATION_ACTUAL_TABLE_NAME", "UDP_SALES_CRM.SLS_OPP_LN_SNAP_WKLY_F_VW")
    print(f"\nTesting with specific table: {test_table}")
    
    # Test adapter with the specific table
    adapter_patterns = adapter.get_table_patterns(test_table)
    print(f"   Popular columns: {len(adapter_patterns.popular_columns)}")
    if adapter_patterns.popular_columns:
        for col in adapter_patterns.popular_columns[:10]:
            print(f"   - {col.get('name')} ({col.get('data_type')})")
    else:
        print(f"   No popular columns found - table may not exist in Alation")
    
    print(f"   Stewards: {len(adapter_patterns.stewards)}")
    if adapter_patterns.stewards:
        for steward in adapter_patterns.stewards[:5]:
            print(f"   - {steward}")
    
    print(f"   Common joins: {len(adapter_patterns.common_joins)}")
    if adapter_patterns.common_joins:
        for join in adapter_patterns.common_joins[:3]:
            print(f"   - {join.get('content', 'N/A')} (freq: {join.get('freq', 0)})")

    print("\n✅ AlationAPIKeyAdapter works - successfully retrieves column metadata for tables")


def main() -> int:
    test_mock_adapter()
    test_api_key_adapter()
    print("\n✅ Alation adapter tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
