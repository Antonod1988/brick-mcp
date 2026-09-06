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
    with patch("brick_mcp._helpers._find_ldview", return_value=None):
        yield


@pytest.fixture(autouse=True)
def _native_transport_stub():
    """Unit tests isolate the process transport; native_bridge/probe.py tests Studio."""
    with patch(
        "brick_mcp.tools.studio_check.run_native_check",
        return_value={
            "source": "native_studio_runtime",
            "status": "clear",
            "warnings": 0,
            "cautions": 0,
            "stability_issues": 0,
            "detached_sections": 0,
        },
    ):
        yield
