"""Test configuration and shared fixtures.

This module provides test fixtures and configuration for the entire test suite.
The autouse fixtures here run automatically for every test.
"""

import pytest


@pytest.fixture(autouse=True)
def reset_state():
    """Clear any module-level state between tests.

    This fixture runs automatically before each test to ensure test isolation.
    As we identify caches or state that needs clearing, we'll add them here.
    """
    # Clear any module-level caches (add as needed)
    yield
    # Cleanup after test (add as needed)
