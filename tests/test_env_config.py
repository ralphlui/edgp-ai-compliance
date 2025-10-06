#!/usr/bin/env python3
"""
Test script to demonstrate environment-specific configuration loading
"""

import os
import sys
from pathlib import Path

# Add src to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_environment_loading():
    """Test different environment configurations"""
    
    print("🧪 Testing Environment-Specific Configuration Loading")
    print("=" * 60)
    
    # Test 1: Default environment
    print("\n1️⃣  Testing DEFAULT environment:")
    os.environ.pop("APP_ENV", None)  # Remove if exists
    from config.settings import create_settings
    settings = create_settings()
    print(f"   APP_ENV: {settings.app_env}")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")
    
    # Test 2: Development environment
    print("\n2️⃣  Testing DEVELOPMENT environment:")
    os.environ["APP_ENV"] = "development"
    settings = create_settings()
    print(f"   APP_ENV: {settings.app_env}")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")
    
    # Test 3: SIT environment
    print("\n3️⃣  Testing SIT environment:")
    os.environ["APP_ENV"] = "sit"
    settings = create_settings()
    print(f"   APP_ENV: {settings.app_env}")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")
    
    # Test 4: Production environment
    print("\n4️⃣  Testing PRODUCTION environment:")
    os.environ["APP_ENV"] = "production"
    settings = create_settings()
    print(f"   APP_ENV: {settings.app_env}")
    print(f"   Environment: {settings.environment}")
    print(f"   Debug: {settings.debug}")
    
    # Test 5: Command-line override
    print("\n5️⃣  Testing COMMAND-LINE overrides:")
    os.environ["APP_ENV"] = "production"
    os.environ["AWS_REGION"] = "eu-west-1"
    os.environ["AI_AGENT_API_KEY"] = "test_key_123"
    settings = create_settings()
    print(f"   APP_ENV: {settings.app_env}")
    print(f"   AWS_REGION: {settings.aws_region}")
    print(f"   AI_AGENT_API_KEY: {'***' + settings.ai_agent_api_key[-4:] if settings.ai_agent_api_key else 'Not set'}")
    
    print("\n✅ All tests completed!")
    print("\n💡 Usage Examples:")
    print("   # Use development environment:")
    print("   uv run python -m main --app-env development")
    print("")
    print("   # Use SIT with custom AWS region:")
    print("   uv run python -m main --app-env sit --aws-region ap-southeast-1")
    print("")
    print("   # Use production with all parameters:")
    print("   uv run python -m main \\")
    print("     --app-env production \\")
    print("     --aws-region ap-southeast-1 \\")
    print("     --aws-access-key-id AKIAXXXXXXXX \\")
    print("     --aws-secret-access-key your_secret_key \\")
    print("     --ai-agent-api-key your_ai_api_key")

if __name__ == "__main__":
    test_environment_loading()