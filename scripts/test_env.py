#!/usr/bin/env python3
"""
Environment Configuration Test Script

Tests and validates all environment variables and connections.
Run this after configuring .env to ensure everything is set up correctly.

Usage:
    python scripts/test_env.py
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_header(title: str) -> None:
    """Print formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")


def print_status(check: str, passed: bool, message: str = "") -> None:
    """Print check status with color."""
    status = "✅ PASS" if passed else "❌ FAIL"
    full_message = f"{status} | {check}"
    if message:
        full_message += f": {message}"
    print(full_message)


def load_env() -> bool:
    """Load .env file and verify it exists."""
    env_path = project_root / ".env"
    
    if not env_path.exists():
        print_status("Load .env file", False, ".env file not found")
        print(f"\n💡 Create .env from .env.example:")
        print(f"   cp .env.example .env")
        return False
    
    # Load dotenv if available
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        print_status("Load .env file", True, f"Loaded from {env_path}")
        return True
    except ImportError:
        print("⚠️  python-dotenv not installed. Reading .env manually...")
        # Manual parsing
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
        print_status("Load .env file", True, "Loaded manually")
        return True


def check_required_vars() -> Tuple[bool, List[str]]:
    """Check all required environment variables."""
    print_header("Required Environment Variables")
    
    all_passed = True
    missing_vars = []
    
    # IOMETE variables (OAuth OR Token auth)
    iomete_oauth = bool(
        os.getenv("IOMETE_CLIENT_ID") and 
        os.getenv("IOMETE_CLIENT_SECRET")
    )
    iomete_token = bool(
        os.getenv("IOMETE_USER_ID") and 
        os.getenv("IOMETE_API_TOKEN")
    )
    
    if iomete_oauth or iomete_token:
        auth_method = "OAuth2" if iomete_oauth else "API Token"
        print_status("IOMETE Authentication", True, f"Using {auth_method}")
    else:
        print_status("IOMETE Authentication", False, 
                    "Need either CLIENT_ID+SECRET or USER_ID+TOKEN")
        all_passed = False
        missing_vars.extend([
            "IOMETE_CLIENT_ID/SECRET or IOMETE_USER_ID/TOKEN"
        ])
    
    # IOMETE infrastructure
    required_iomete = {
        "IOMETE_HOST": "IOMETE host endpoint",
        "IOMETE_DATA_PLANE": "Data plane ID",
        "IOMETE_LAKEHOUSE": "Lakehouse name",
        "IOMETE_CATALOG": "Catalog name",
        "IOMETE_NAMESPACE": "Namespace/schema"
    }
    
    for var, desc in required_iomete.items():
        value = os.getenv(var)
        if value and not value.startswith("your_"):
            print_status(f"{var}", True, f"{desc}: {value[:30]}...")
        else:
            print_status(f"{var}", False, f"Missing or placeholder: {desc}")
            all_passed = False
            missing_vars.append(var)
    
    # LLM variables
    print()
    llm_provider = os.getenv("LLM_PROVIDER", "custom")
    print(f"LLM Provider: {llm_provider}")
    
    if llm_provider == "custom":
        llm_custom = {
            "LLM_CLIENT_ID": "LLM OAuth client ID",
            "LLM_CLIENT_SECRET": "LLM OAuth secret",
            "LLM_BASE_URL": "LLM API endpoint"
        }
        for var, desc in llm_custom.items():
            value = os.getenv(var)
            if value and not value.startswith("your_"):
                print_status(f"{var}", True, f"{desc}")
            else:
                print_status(f"{var}", False, f"Missing: {desc}")
                all_passed = False
                missing_vars.append(var)
    
    elif llm_provider == "openai":
        key = os.getenv("OPENAI_API_KEY")
        if key and key.startswith("sk-"):
            print_status("OPENAI_API_KEY", True, "Set")
        else:
            print_status("OPENAI_API_KEY", False, "Missing or invalid")
            all_passed = False
            missing_vars.append("OPENAI_API_KEY")
    
    elif llm_provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        if key and key.startswith("sk-ant-"):
            print_status("ANTHROPIC_API_KEY", True, "Set")
        else:
            print_status("ANTHROPIC_API_KEY", False, "Missing or invalid")
            all_passed = False
            missing_vars.append("ANTHROPIC_API_KEY")
    
    elif llm_provider == "azure":
        azure_vars = ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"]
        for var in azure_vars:
            if os.getenv(var):
                print_status(var, True, "Set")
            else:
                print_status(var, False, "Missing")
                all_passed = False
                missing_vars.append(var)
    
    return all_passed, missing_vars


def check_optional_vars() -> None:
    """Check optional but recommended variables."""
    print_header("Optional Configuration")
    
    optional = {
        "LOG_LEVEL": "INFO",
        "ENVIRONMENT": "development",
        "ENABLE_CACHING": "true",
        "QUERY_TIMEOUT_SECONDS": "30"
    }
    
    for var, default in optional.items():
        value = os.getenv(var, default)
        print(f"  {var}: {value}")


def test_iomete_connection() -> bool:
    """Test actual connection to IOMETE."""
    print_header("IOMETE Connection Test")
    
    try:
        # Check if SSL cert file exists
        cert_file = os.getenv("IOMETE_CERT_FILE")
        verify_ssl = os.getenv("IOMETE_VERIFY_SSL", "true").lower() == "true"
        
        if cert_file and verify_ssl:
            cert_path = project_root / cert_file
            if cert_path.exists():
                print_status("SSL Certificate", True, f"Found: {cert_file}")
            else:
                print_status("SSL Certificate", False, 
                           f"Not found: {cert_file}")
                print(f"   💡 Either place cert at {cert_path} or set "
                      f"IOMETE_VERIFY_SSL=false")
        
        # TODO: Add actual connection test when IOMETE connector is available
        print("\n⏳ Skipping actual connection test (connector not imported)")
        print("   This will test the real connection once implemented.")
        
        return True
        
    except Exception as e:
        print_status("IOMETE Connection", False, str(e))
        return False


def test_llm_connection() -> bool:
    """Test actual connection to LLM."""
    print_header("LLM Connection Test")
    
    provider = os.getenv("LLM_PROVIDER", "custom")
    
    try:
        if provider == "custom":
            base_url = os.getenv("LLM_BASE_URL")
            if base_url:
                print(f"  LLM Endpoint: {base_url}")
                print("  ⏳ Skipping actual API test")
                print("     Add requests.get(base_url) to test connectivity")
            else:
                print_status("LLM Configuration", False, 
                           "LLM_BASE_URL not set")
                return False
        
        elif provider == "openai":
            print("  OpenAI provider configured")
            print("  ⏳ Install openai package to test: pip install openai")
        
        elif provider == "anthropic":
            print("  Anthropic provider configured")
            print("  ⏳ Install anthropic package to test: pip install anthropic")
        
        elif provider == "azure":
            print("  Azure OpenAI provider configured")
            print("  ⏳ Install openai package to test: pip install openai")
        
        return True
        
    except Exception as e:
        print_status("LLM Connection", False, str(e))
        return False


def check_directories() -> bool:
    """Check if required directories exist."""
    print_header("Directory Structure")
    
    all_exist = True
    required_dirs = [
        "data",
        "logs",
        "knowledge",
        "scripts"
    ]
    
    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print_status(f"{dir_name}/", True, f"Exists: {dir_path}")
        else:
            print_status(f"{dir_name}/", False, f"Missing: {dir_path}")
            auto_create = os.getenv("AUTO_CREATE_DB_DIRS", "true").lower()
            if auto_create == "true":
                print(f"   💡 Creating directory...")
                dir_path.mkdir(parents=True, exist_ok=True)
                print(f"   ✅ Created: {dir_path}")
            else:
                all_exist = False
    
    return all_exist


def main() -> int:
    """Run all tests."""
    print("\n" + "=" * 80)
    print("  Smart Table Analyzer - Environment Configuration Test")
    print("=" * 80)
    
    # Load .env
    if not load_env():
        return 1
    
    # Check required variables
    vars_passed, missing = check_required_vars()
    
    # Check optional variables
    check_optional_vars()
    
    # Check directories
    dirs_ok = check_directories()
    
    # Test connections
    iomete_ok = test_iomete_connection()
    llm_ok = test_llm_connection()
    
    # Summary
    print_header("Summary")
    
    if vars_passed and dirs_ok:
        print("✅ All required configuration is set!")
        print("\n📋 Next steps:")
        print("   1. Verify IOMETE connection works with real queries")
        print("   2. Test LLM API calls")
        print("   3. Run the analyzer on a test table")
        print("\n💡 See ENV_QUICK_START.md for detailed setup guide")
        return 0
    else:
        print("❌ Configuration incomplete\n")
        if missing:
            print("Missing or invalid variables:")
            for var in missing:
                print(f"   • {var}")
        print("\n💡 Edit .env and fill in the required values")
        print("💡 See ENV_QUICK_START.md for help")
        return 1


if __name__ == "__main__":
    sys.exit(main())
