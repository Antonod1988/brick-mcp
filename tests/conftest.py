"""Test fixtures for brick-mcp tests."""

from __future__ import annotations

import pytest

from brick_mcp.model import StudioProject, set_model


@pytest.fixture(autouse=True)
def fresh_model():
    """Reset the global model singleton to a fresh empty model before each test."""
    project = StudioProject.new("test_model")
    set_model(project)
    yield
    set_model(None)
