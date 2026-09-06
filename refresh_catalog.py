"""Rebuild the small catalog snapshot after updating Studio's parts library."""

import json
import os
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from brick_mcp.catalog import _load_from_directory

config_path = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
env = tomllib.loads(config_path.read_text(encoding="utf-8"))["mcp_servers"]["brick"][
    "env"
]
catalog = _load_from_directory(env["LDRAW_LIBRARY_PATH"])
assert len(catalog) > 0, "Library is empty; keep the existing snapshot"
destination = Path(__file__).parent / ".cache" / "studio-catalog.json"
destination.parent.mkdir(exist_ok=True)
temporary = destination.with_suffix(".tmp")
temporary.write_text(json.dumps(catalog, ensure_ascii=False), encoding="utf-8")
temporary.replace(destination)
print(f"Indexed {len(catalog)} parts: {destination}")
