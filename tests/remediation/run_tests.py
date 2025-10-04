#!/usr/bin/env python3
"""
Test runner for remediation agent unit tests
"""

import os
import sys
import pytest
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def run_remediation_tests():
    """Run all remediation agent unit tests"""
    test_dir = Path(__file__).parent / "unit"
    
    # Test configuration
    pytest_args = [
        str(test_dir),
        "-v",  # Verbose output
        "--tb=short",  # Short traceback format
        "--strict-markers",  # Strict marker checking
        "--disable-warnings",  # Disable pytest warnings
        "-x",  # Stop on first failure (optional)
        "--cov=src/remediation_agent",  # Coverage for remediation agent (if coverage installed)
        "--cov-report=term-missing",  # Show missing lines in coverage
        "--cov-report=html:htmlcov/remediation",  # HTML coverage report
    ]
    
    print("🧪 Running Remediation Agent Unit Tests...")
    print(f"📁 Test Directory: {test_dir}")
    print("=" * 80)
    
    # Run pytest
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0:
        print("\n" + "=" * 80)
        print("✅ All remediation agent tests passed!")
        print("📊 Coverage report generated in htmlcov/remediation/")
    else:
        print("\n" + "=" * 80)
        print("❌ Some tests failed. Check the output above.")
    
    return exit_code

def run_specific_test_file(test_file: str):
    """Run tests from a specific test file"""
    test_path = Path(__file__).parent / "unit" / test_file
    
    if not test_path.exists():
        print(f"❌ Test file not found: {test_path}")
        return 1
    
    pytest_args = [
        str(test_path),
        "-v",
        "--tb=short",
        "--disable-warnings"
    ]
    
    print(f"🧪 Running tests from: {test_file}")
    print("=" * 80)
    
    return pytest.main(pytest_args)

def run_specific_test_class(test_file: str, test_class: str):
    """Run tests from a specific test class"""
    test_path = Path(__file__).parent / "unit" / test_file
    
    pytest_args = [
        f"{test_path}::{test_class}",
        "-v",
        "--tb=short",
        "--disable-warnings"
    ]
    
    print(f"🧪 Running test class: {test_class} from {test_file}")
    print("=" * 80)
    
    return pytest.main(pytest_args)

def main():
    """Main test runner entry point"""
    if len(sys.argv) == 1:
        # Run all tests
        return run_remediation_tests()
    elif len(sys.argv) == 2:
        # Run specific test file
        test_file = sys.argv[1]
        if not test_file.startswith("test_"):
            test_file = f"test_{test_file}.py"
        elif not test_file.endswith(".py"):
            test_file = f"{test_file}.py"
        return run_specific_test_file(test_file)
    elif len(sys.argv) == 3:
        # Run specific test class
        test_file, test_class = sys.argv[1], sys.argv[2]
        if not test_file.startswith("test_"):
            test_file = f"test_{test_file}.py"
        elif not test_file.endswith(".py"):
            test_file = f"{test_file}.py"
        return run_specific_test_class(test_file, test_class)
    else:
        print("Usage:")
        print("  python run_tests.py                    # Run all tests")
        print("  python run_tests.py models             # Run test_models.py")
        print("  python run_tests.py models TestModels  # Run TestModels class from test_models.py")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)