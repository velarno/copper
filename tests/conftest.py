"""
Global test configuration and fixtures.

This file ensures critical system checks run before any tests execute.
"""

import pytest
import asyncio

from api.stac.crud import is_catalog_loaded
from api.stac.client import async_stac_client, init_all_collections


def pytest_configure(config):
    """Configure pytest with custom markers and early validation."""
    config.addinivalue_line(
        "markers", "critical: marks tests as critical system checks"
    )


def pytest_sessionstart(session):
    """
    Run critical checks at the start of the test session.

    This ensures the entire test suite fails early if critical system
    requirements are not met.
    """
    try:
        if not is_catalog_loaded():
            collections = asyncio.run(init_all_collections())
            async_stac_client.persist_all(collections)
    except Exception:
        pytest.fail(
            "Failed to load STAC catalog and its collections, most tests will fail."
        )


@pytest.fixture(scope="session", autouse=True)
def ensure_catalog_loaded():
    """
    Ensure the STAC catalog is loaded before running any tests.

    This fixture runs automatically for all tests and will cause
    the entire test suite to fail if the catalog is not loaded.
    """
    try:
        if not is_catalog_loaded():
            pytest.fail(
                "CRITICAL: STAC catalog is not loaded. "
                "All tests will fail. "
                "Please ensure the catalog is initialized before running tests.\n"
                "You may need to run: python -m api.stac.commands init"
            )
        return True
    except Exception as e:
        pytest.fail(
            f"CRITICAL: Failed to check if STAC catalog is loaded: {e}\n"
            "This indicates a serious system configuration issue. "
            "Please check your database connection and STAC configuration."
        )


@pytest.fixture(scope="session")
def catalog_status():
    """
    Provide catalog status information to tests.

    This fixture can be used by tests that need to know about
    the catalog state without re-checking it.
    """
    return {
        "loaded": is_catalog_loaded(),
        "message": "STAC catalog is properly loaded and accessible",
    }
