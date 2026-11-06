#!/usr/bin/env python3
"""
Test Runner for PS-113 School Fee Management Engine
Discovers and executes all unit and integration tests across BR-01 through BR-12.
"""
import sys
import unittest

def run_all_tests():
    print("=" * 70)
    print("RUNNING PS-113 FEE MANAGEMENT ENGINE UNIT & EDGE CASE TEST SUITE")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = loader.discover("tests", pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print(f"TESTS RUN: {result.testsRun}")
    print(f"SUCCESSES: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"FAILURES : {len(result.failures)}")
    print(f"ERRORS   : {len(result.errors)}")
    print("=" * 70)

    if not result.wasSuccessful():
        sys.exit(1)

if __name__ == "__main__":
    run_all_tests()
