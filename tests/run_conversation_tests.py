#!/usr/bin/env python3
"""
Test runner for conversation handler components
"""

import sys
import subprocess
import argparse
from pathlib import Path


def run_tests(test_pattern=None, verbose=False, coverage=False, parallel=False):
    """
    Run conversation handler tests
    
    Args:
        test_pattern: Pattern to match test files/functions
        verbose: Enable verbose output
        coverage: Enable coverage reporting
        parallel: Run tests in parallel
    """
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Test files to run
    test_files = [
        "tests/test_conversation_state_machine.py",
        "tests/test_intent_classifier.py", 
        "tests/test_message_handler.py",
        "tests/test_escalation_service.py"
    ]
    
    # Add test pattern if specified
    if test_pattern:
        test_files = [f for f in test_files if test_pattern in f]
        if not test_files:
            # If no files match, treat as function pattern
            cmd.extend(["-k", test_pattern])
            test_files = [
                "tests/test_conversation_state_machine.py",
                "tests/test_intent_classifier.py", 
                "tests/test_message_handler.py",
                "tests/test_escalation_service.py"
            ]
    
    # Add test files
    cmd.extend(test_files)
    
    # Add options
    if verbose:
        cmd.append("-v")
    
    if coverage:
        cmd.extend([
            "--cov=app.services.conversation_service",
            "--cov=app.services.conversation_state_machine", 
            "--cov=app.services.message_handler",
            "--cov=app.services.escalation_service",
            "--cov=app.utils.intent_classifier",
            "--cov=app.utils.context_manager",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    if parallel:
        cmd.extend(["-n", "auto"])
    
    # Add other useful options
    cmd.extend([
        "--tb=short",  # Shorter traceback format
        "--strict-markers",  # Strict marker checking
        "--disable-warnings"  # Disable warnings for cleaner output
    ])
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 80)
    
    # Run the tests
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        return 1
    except Exception as e:
        print(f"Error running tests: {e}")
        return 1


def run_specific_test_suites():
    """Run specific test suites"""
    
    test_suites = {
        "state_machine": {
            "description": "Conversation state machine tests",
            "files": ["tests/test_conversation_state_machine.py"],
            "markers": []
        },
        "intent": {
            "description": "Intent classification tests", 
            "files": ["tests/test_intent_classifier.py"],
            "markers": []
        },
        "handler": {
            "description": "Message handler tests",
            "files": ["tests/test_message_handler.py"], 
            "markers": []
        },
        "escalation": {
            "description": "Escalation service tests",
            "files": ["tests/test_escalation_service.py"],
            "markers": []
        },
        "integration": {
            "description": "Integration tests",
            "files": [
                "tests/test_conversation_state_machine.py",
                "tests/test_intent_classifier.py",
                "tests/test_message_handler.py"
            ],
            "markers": ["integration"]
        }
    }
    
    print("Available test suites:")
    print("-" * 40)
    
    for suite_name, suite_info in test_suites.items():
        print(f"{suite_name:15} - {suite_info['description']}")
    
    print("\nUsage examples:")
    print("  python tests/run_conversation_tests.py --suite state_machine")
    print("  python tests/run_conversation_tests.py --suite intent --verbose")
    print("  python tests/run_conversation_tests.py --suite integration --coverage")
    
    return test_suites


def main():
    """Main test runner function"""
    
    parser = argparse.ArgumentParser(
        description="Run conversation handler tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all conversation tests
  python tests/run_conversation_tests.py
  
  # Run with verbose output and coverage
  python tests/run_conversation_tests.py --verbose --coverage
  
  # Run specific test file
  python tests/run_conversation_tests.py --pattern state_machine
  
  # Run specific test function
  python tests/run_conversation_tests.py --pattern test_transition_to_valid_state
  
  # Run tests in parallel
  python tests/run_conversation_tests.py --parallel
  
  # Run specific test suite
  python tests/run_conversation_tests.py --suite intent
        """
    )
    
    parser.add_argument(
        "--pattern", "-p",
        help="Pattern to match test files or functions"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--coverage", "-c", 
        action="store_true",
        help="Enable coverage reporting"
    )
    
    parser.add_argument(
        "--parallel", "-j",
        action="store_true", 
        help="Run tests in parallel"
    )
    
    parser.add_argument(
        "--suite", "-s",
        help="Run specific test suite (use --list-suites to see available)"
    )
    
    parser.add_argument(
        "--list-suites",
        action="store_true",
        help="List available test suites"
    )
    
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Run quick tests only (skip slow integration tests)"
    )
    
    args = parser.parse_args()
    
    # List available test suites
    if args.list_suites:
        run_specific_test_suites()
        return 0
    
    # Handle test suite selection
    if args.suite:
        test_suites = run_specific_test_suites()
        if args.suite not in test_suites:
            print(f"Error: Unknown test suite '{args.suite}'")
            print("Use --list-suites to see available suites")
            return 1
        
        suite_info = test_suites[args.suite]
        print(f"Running test suite: {args.suite}")
        print(f"Description: {suite_info['description']}")
        print("-" * 80)
        
        # Run suite-specific tests
        cmd = ["python", "-m", "pytest"] + suite_info['files']
        
        if args.verbose:
            cmd.append("-v")
        if args.coverage:
            cmd.extend(["--cov=app", "--cov-report=term-missing"])
        if suite_info['markers']:
            cmd.extend(["-m", " or ".join(suite_info['markers'])])
        
        result = subprocess.run(cmd, check=False)
        return result.returncode
    
    # Handle quick tests
    if args.quick:
        args.pattern = "not slow"
    
    # Run tests
    return run_tests(
        test_pattern=args.pattern,
        verbose=args.verbose,
        coverage=args.coverage,
        parallel=args.parallel
    )


if __name__ == "__main__":
    sys.exit(main())
