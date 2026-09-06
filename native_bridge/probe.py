"""Run real Studio checks on known connected and disconnected two-brick cases."""

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.environ["BRICK_STUDIO_BRIDGE_DIR"] = str(ROOT / ".cache/studio-worker/jobs")
from brick_mcp.model import StudioProject
from brick_mcp.native_studio import run_native_check

heartbeat = Path(os.environ["BRICK_STUDIO_BRIDGE_DIR"]) / "bridge.json"
deadline = time.monotonic() + 60
while time.monotonic() < deadline:
    try:
        if json.loads(heartbeat.read_text())["status"] == "ready":
            break
    except OSError, ValueError:
        pass
    time.sleep(1)
results = {}
for label, x in [("connected", 0), ("detached", 160)]:
    project = StudioProject.new(label)
    project.add_part(None, "3001", 4, 0, 0, 0)
    project.add_part(None, "3001", 14, x, -24, 60 if x else 0)
    report = run_native_check(project)
    print(label, json.dumps(report), flush=True)
    results[label] = report
    assert (report["status"] == "clear") == (label == "connected"), report
    if label == "detached":
        assert report["detached_parts"][0]["z"] == 60
(ROOT / ".cache/native-probes.json").write_text(json.dumps(results, indent=2))
