"""Test fixtures for brick-mcp tests."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from brick_mcp.model import StudioProject, set_model


@pytest.fixture(autouse=True)
def fresh_model():
    """Reset the global model singleton to a fresh empty model before each test."""
    project = StudioProject.new("test_model")
    set_model(project)
    yield
    set_model(None)


@pytest.fixture(autouse=True)
def _no_ldview():
    """Prevent try_render from finding ldview so mutation tools return plain dicts."""
    with patch("brick_mcp._helpers.shutil.which", return_value=None):
        yield
