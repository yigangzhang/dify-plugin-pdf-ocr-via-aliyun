#!/usr/bin/env python3
"""
Test runner script for Smart Document Parser Plugin.
Follows Dify plugin testing guidelines.
"""
import os
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run shell command and return result."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=cwd,
            capture_output=True, 
            text=True,
            check=True
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr


def install_dependencies():
    """Install test dependencies."""
    print("📦 Installing dependencies...")
    
    # Install main dependencies
    returncode, stdout, stderr = run_command("pip install -r requirements.txt")
    
    if returncode != 0:
        print(f"❌ Failed to install dependencies:")
        print(stderr)
        return False
    
    print("✅ Dependencies installed successfully")
    return True


def run_linting():
    """Run code linting checks."""
    print("🔍 Running linting checks...")
    
    # Check if flake8 is available
    returncode, _, _ = run_command("python -m flake8 --version")
    
    if returncode == 0:
        print("  Running flake8...")
        returncode, stdout, stderr = run_command(
            "python -m flake8 tools/ --max-line-length=120 --ignore=E501,W503"
        )
        
        if returncode != 0:
            print("❌ Flake8 found issues:")
            print(stdout)
            return False
        else:
            print("✅ Flake8 passed")
    else:
        print("⚠️  flake8 not available, skipping")
    
    return True


def run_unit_tests():
    """Run unit tests."""
    print("🧪 Running unit tests...")
    
    returncode, stdout, stderr = run_command(
        "python -m pytest tests/test_smart_doc_parser.py -v -m unit"
    )
    
    if returncode != 0:
        print("❌ Unit tests failed:")
        print(stdout)
        print(stderr)
        return False
    
    print("✅ Unit tests passed")
    return True


def run_integration_tests():
    """Run integration tests."""
    print("🔗 Running integration tests...")
    
    returncode, stdout, stderr = run_command(
        "python -m pytest tests/test_integration.py -v -m integration"
    )
    
    if returncode != 0:
        print("❌ Integration tests failed:")
        print(stdout)
        print(stderr)
        return False
    
    print("✅ Integration tests passed")
    return True


def run_e2e_tests():
    """Run end-to-end tests."""
    print("🎯 Running end-to-end tests...")
    
    returncode, stdout, stderr = run_command(
        "python -m pytest tests/test_end_to_end.py -v"
    )
    
    if returncode != 0:
        print("❌ End-to-end tests failed:")
        print(stdout)
        print(stderr)
        return False
    
    print("✅ End-to-end tests passed")
    return True


def run_coverage_report():
    """Generate test coverage report."""
    print("📊 Generating coverage report...")
    
    returncode, stdout, stderr = run_command(
        "python -m pytest tests/ --cov=tools --cov=provider --cov-report=term-missing --cov-report=html"
    )
    
    if returncode == 0:
        print("✅ Coverage report generated")
        print("📂 HTML report available in htmlcov/index.html")
    else:
        print("⚠️  Coverage report generation failed")
        print(stderr)
    
    return True


def run_api_tests():
    """Run tests that require API credentials (optional)."""
    api_key = os.getenv("ALIYUN_API_KEY")
    
    if not api_key:
        print("⏭️  Skipping API tests (ALIYUN_API_KEY not set)")
        return True
    
    print("🌐 Running API integration tests...")
    
    returncode, stdout, stderr = run_command(
        "python -m pytest tests/ -v -m requires_api"
    )
    
    if returncode != 0:
        print("❌ API tests failed:")
        print(stdout)
        print(stderr)
        return False
    
    print("✅ API tests passed")
    return True


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Smart Document Parser Plugin Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run only unit tests")
    parser.add_argument("--integration", action="store_true", help="Run only integration tests") 
    parser.add_argument("--e2e", action="store_true", help="Run only end-to-end tests")
    parser.add_argument("--api", action="store_true", help="Run only API tests")
    parser.add_argument("--coverage", action="store_true", help="Generate coverage report")
    parser.add_argument("--lint", action="store_true", help="Run linting only")
    parser.add_argument("--install", action="store_true", help="Install dependencies only")
    parser.add_argument("--all", action="store_true", help="Run all tests (default)")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    
    args = parser.parse_args()
    
    # Set default to run all if no specific test type selected
    if not any([args.unit, args.integration, args.e2e, args.api, args.coverage, args.lint, args.install]):
        args.all = True
    
    print("🚀 Smart Document Parser Plugin - Test Suite")
    print("=" * 50)
    
    # Change to project directory
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    success = True
    
    # Install dependencies if requested or running all tests
    if args.install or args.all:
        if not install_dependencies():
            return 1
    
    # Run linting
    if args.lint or args.all:
        if not run_linting():
            success = False
    
    # Run unit tests
    if args.unit or args.all:
        if not run_unit_tests():
            success = False
    
    # Run integration tests
    if args.integration or args.all:
        if not run_integration_tests():
            success = False
    
    # Run end-to-end tests
    if args.e2e or args.all:
        if not run_e2e_tests():
            success = False
    
    # Run API tests
    if args.api or args.all:
        if not run_api_tests():
            success = False
    
    # Generate coverage report
    if args.coverage or args.all:
        run_coverage_report()
    
    print("\n" + "=" * 50)
    
    if success:
        print("🎉 All tests completed successfully!")
        return 0
    else:
        print("💥 Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
