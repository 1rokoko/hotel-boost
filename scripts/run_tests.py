#!/usr/bin/env python3
"""
Comprehensive test runner for Hotel WhatsApp Bot
Provides various test execution modes and reporting
"""

import os
import sys
import argparse
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Any, Optional


class TestRunner:
    """Advanced test runner with multiple execution modes"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_dir = self.project_root / "tests"
        self.coverage_dir = self.project_root / "htmlcov"

        # Test categories and their markers
        self.test_categories = {
            "unit": {
                "marker": "unit",
                "description": "Unit tests for individual components",
                "timeout": 300
            },
            "integration": {
                "marker": "integration",
                "description": "Integration tests for database operations",
                "timeout": 600
            },
            "security": {
                "marker": "security",
                "description": "Security and authentication tests",
                "timeout": 300
            },
            "performance": {
                "marker": "performance and not stress",
                "description": "Performance tests (excluding stress tests)",
                "timeout": 900
            },
            "stress": {
                "marker": "stress",
                "description": "Stress tests under extreme load",
                "timeout": 1800
            },
            "smoke": {
                "marker": "smoke",
                "description": "Quick smoke tests for basic functionality",
                "timeout": 120
            },
            "e2e": {
                "marker": "e2e",
                "description": "End-to-end workflow tests",
                "timeout": 1200
            }
        }

    def run_command(self, cmd: List[str], timeout: Optional[int] = None) -> subprocess.CompletedProcess:
        """Run a command with optional timeout"""
        print(f"Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result
        except subprocess.TimeoutExpired:
            print(f"Command timed out after {timeout} seconds")
            raise

    def setup_environment(self):
        """Setup test environment"""
        env_vars = {
            "ENVIRONMENT": "test",
            "DATABASE_URL": "postgresql+asyncpg://postgres:password@localhost:5432/hotel_bot_test",
            "REDIS_URL": "redis://localhost:6379",
            "SECRET_KEY": "test-secret-key-for-testing-only",
            "PYTHONPATH": str(self.project_root)
        }

        for key, value in env_vars.items():
            os.environ[key] = value

        print("Test environment configured")

    def run_linting(self) -> bool:
        """Run code linting checks"""
        print("\n=== Running Linting Checks ===")

        checks = [
            {
                "name": "flake8 (errors)",
                "cmd": ["flake8", "app", "--count", "--select=E9,F63,F7,F82", "--show-source", "--statistics"]
            },
            {
                "name": "flake8 (warnings)",
                "cmd": ["flake8", "app", "--count", "--exit-zero", "--max-complexity=10", "--max-line-length=88", "--statistics"]
            },
            {
                "name": "black format check",
                "cmd": ["black", "--check", "app"]
            },
            {
                "name": "isort import check",
                "cmd": ["isort", "--check-only", "app"]
            },
            {
                "name": "mypy type check",
                "cmd": ["mypy", "app"]
            }
        ]

        all_passed = True
        for check in checks:
            print(f"\nRunning {check['name']}...")
            result = self.run_command(check["cmd"])

            if result.returncode != 0:
                print(f"❌ {check['name']} failed")
                print(result.stdout)
                print(result.stderr)
                all_passed = False
            else:
                print(f"✅ {check['name']} passed")

        return all_passed

    def run_security_checks(self) -> bool:
        """Run security checks"""
        print("\n=== Running Security Checks ===")

        checks = [
            {
                "name": "bandit security scan",
                "cmd": ["bandit", "-r", "app", "-f", "json", "-o", "bandit-report.json"]
            },
            {
                "name": "safety dependency check",
                "cmd": ["safety", "check", "--json", "--output", "safety-report.json"]
            }
        ]

        all_passed = True
        for check in checks:
            print(f"\nRunning {check['name']}...")
            result = self.run_command(check["cmd"])

            if result.returncode != 0:
                print(f"❌ {check['name']} failed")
                print(result.stdout)
                print(result.stderr)
                all_passed = False
            else:
                print(f"✅ {check['name']} passed")

        return all_passed

    def run_test_category(self, category: str, verbose: bool = True, coverage: bool = True) -> bool:
        """Run tests for a specific category"""
        if category not in self.test_categories:
            print(f"Unknown test category: {category}")
            return False

        config = self.test_categories[category]
        print(f"\n=== Running {category.title()} Tests ===")
        print(f"Description: {config['description']}")

        cmd = ["pytest"]

        # Add test directory or specific marker
        if category == "unit":
            cmd.append("tests/unit/")
        elif category == "integration":
            cmd.append("tests/integration/")
        elif category == "security":
            cmd.append("tests/security/")
        elif category == "performance":
            cmd.append("tests/performance/")
        else:
            cmd.extend(["-m", config["marker"]])

        # Add common options
        if verbose:
            cmd.append("-v")

        cmd.extend([
            "--tb=short",
            "--durations=10",
            f"--timeout={config['timeout']}"
        ])

        # Add coverage options
        if coverage:
            cmd.extend([
                "--cov=app",
                "--cov-append",
                "--cov-report=term-missing"
            ])

        start_time = time.time()
        result = self.run_command(cmd, timeout=config["timeout"] + 60)
        duration = time.time() - start_time

        if result.returncode == 0:
            print(f"✅ {category.title()} tests passed in {duration:.2f}s")
            return True
        else:
            print(f"❌ {category.title()} tests failed in {duration:.2f}s")
            print(result.stdout)
            print(result.stderr)
            return False

    def generate_coverage_report(self):
        """Generate comprehensive coverage report"""
        print("\n=== Generating Coverage Report ===")

        cmd = [
            "pytest", "--cov=app",
            "--cov-report=html:htmlcov",
            "--cov-report=xml:coverage.xml",
            "--cov-report=term-missing",
            "--cov-fail-under=85",
            "tests/"
        ]

        result = self.run_command(cmd)

        if result.returncode == 0:
            print("✅ Coverage report generated successfully")
            print(f"HTML report: {self.coverage_dir}/index.html")
        else:
            print("❌ Coverage report generation failed")
            print(result.stdout)
            print(result.stderr)

    def run_all_tests(self, include_stress: bool = False, include_linting: bool = True) -> bool:
        """Run all test categories"""
        print("=== Running Complete Test Suite ===")

        all_passed = True

        # Setup environment
        self.setup_environment()

        # Run linting if requested
        if include_linting:
            if not self.run_linting():
                all_passed = False

        # Run security checks
        if not self.run_security_checks():
            all_passed = False

        # Run test categories
        categories_to_run = ["smoke", "unit", "integration", "security", "performance", "e2e"]
        if include_stress:
            categories_to_run.append("stress")

        for category in categories_to_run:
            if not self.run_test_category(category):
                all_passed = False

        # Generate final coverage report
        self.generate_coverage_report()

        return all_passed


def main():
    """Main entry point for test runner"""
    parser = argparse.ArgumentParser(
        description="Comprehensive test runner for Hotel WhatsApp Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_tests.py --all                    # Run all tests
  python scripts/run_tests.py --category unit          # Run only unit tests
  python scripts/run_tests.py --category performance   # Run performance tests
  python scripts/run_tests.py --smoke                  # Run smoke tests only
  python scripts/run_tests.py --lint-only              # Run linting only
  python scripts/run_tests.py --all --include-stress   # Include stress tests
        """
    )

    # Test execution modes
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all test categories"
    )

    parser.add_argument(
        "--category",
        choices=["unit", "integration", "security", "performance", "stress", "smoke", "e2e"],
        help="Run specific test category"
    )

    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run smoke tests only (quick validation)"
    )

    parser.add_argument(
        "--lint-only",
        action="store_true",
        help="Run linting and security checks only"
    )

    # Options
    parser.add_argument(
        "--include-stress",
        action="store_true",
        help="Include stress tests (only with --all)"
    )

    parser.add_argument(
        "--no-linting",
        action="store_true",
        help="Skip linting checks"
    )

    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Skip coverage reporting"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Verbose test output (default: True)"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output"
    )

    args = parser.parse_args()

    # Initialize test runner
    runner = TestRunner()

    # Determine execution mode
    success = True

    if args.lint_only:
        print("Running linting and security checks only...")
        runner.setup_environment()
        success = runner.run_linting() and runner.run_security_checks()

    elif args.smoke:
        print("Running smoke tests only...")
        runner.setup_environment()
        success = runner.run_test_category("smoke", verbose=not args.quiet, coverage=not args.no_coverage)

    elif args.category:
        print(f"Running {args.category} tests...")
        runner.setup_environment()
        success = runner.run_test_category(args.category, verbose=not args.quiet, coverage=not args.no_coverage)

    elif args.all:
        print("Running complete test suite...")
        success = runner.run_all_tests(
            include_stress=args.include_stress,
            include_linting=not args.no_linting
        )

    else:
        # Default: run smoke tests
        print("No specific mode selected, running smoke tests...")
        runner.setup_environment()
        success = runner.run_test_category("smoke", verbose=not args.quiet, coverage=not args.no_coverage)

    # Print summary
    print("\n" + "="*60)
    if success:
        print("🎉 All tests completed successfully!")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()