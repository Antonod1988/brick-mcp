"""Local file transport to a dedicated Studio process running its native checks."""

import hashlib
import json
import os
import time
import uuid
import subprocess
import shutil
from pathlib import Path

from brick_mcp.io_file import write_io_file
from brick_mcp.ldraw import PartLine
from brick_mcp.model import StudioProject
from brick_mcp.catalog import get_part_info


def is_canvas(part_number):
    info = get_part_info(part_number) or {}
    return info.get("category", "").casefold() in {
        "canvas",
        "sheet fabric",
    } and info.get("name", "").lower().startswith("sail ")


def _running_worker(root):
    """Check the owned executable, not just a stale PID/heartbeat after reboot."""
    if os.name != "nt":
        return False
    import ctypes
    from ctypes import wintypes

    try:
        pid = int(json.loads((root / "bridge.json").read_text())["pid"])
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.QueryFullProcessImageNameW.argtypes = (
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = wintypes.DWORD(len(buffer))
            return (
                bool(
                    kernel.QueryFullProcessImageNameW(
                        handle, 0, buffer, ctypes.byref(size)
                    )
                )
                and Path(buffer.value).resolve() == root.parent / "StudioWorker.exe"
            )
        finally:
            kernel.CloseHandle(handle)
    except OSError, ValueError, KeyError:
        return False


def run_native_check(
    project,
    submodel=None,
    through_step=None,
    timeout=150,
    include_connectors=False,
    exclude_canvas=False,
):
    root = os.environ.get(
        "BRICK_STUDIO_BRIDGE_DIR",
        str(Path(__file__).resolve().parents[2] / ".cache/studio-worker/jobs"),
    )
    root = Path(root).resolve()
    status_file = root / "bridge.json"
    if "BRICK_STUDIO_BRIDGE_DIR" not in os.environ and not _running_worker(root):
        script = Path(__file__).resolve().parents[2] / "native_bridge/start.ps1"
        subprocess.run(
            [
                shutil.which("pwsh") or "powershell.exe",
                "-NoProfile",
                "-File",
                str(script),
            ],
            check=True,
            timeout=30,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ready_deadline = time.monotonic() + 60
        while time.monotonic() < ready_deadline:
            try:
                if json.loads(status_file.read_text(encoding="utf8"))[
                    "status"
                ] == "ready" and _running_worker(root):
                    break
            except OSError, ValueError, KeyError:
                pass
            time.sleep(0.2)
    try:
        heartbeat = json.loads((root / "bridge.json").read_text(encoding="utf8"))
        if (
            heartbeat["status"] != "ready"
            or time.time() - (root / "bridge.json").stat().st_mtime > 10
        ):
            raise ValueError("Worker is not ready")
    except (OSError, ValueError, KeyError) as exc:
        raise RuntimeError(
            "Native Studio worker is unavailable; no stability result"
        ) from exc
    ident = uuid.uuid4().hex
    path = root / (ident + ".io")
    audit = StudioProject.new("audit-" + ident)
    sd = audit._submodel(None)
    for p in project.flatten(submodel, through_step):
        if exclude_canvas and is_canvas(p["part_number"]):
            continue
        sd.commands.append(
            PartLine(
                p["color"],
                p["x"],
                p["y"],
                p["z"],
                tuple(p["rotation"]),
                p["part_number"],
            )
        )
    sd._rebuild_index()
    if not sd._parts:
        raise ValueError("Cannot perform a native stability check on an empty model")
    write_io_file(str(path), audit.to_ldraw_text(), {}, audit.to_v2_ldraw_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    request = dict(
        path=str(path),
        sha256=digest,
        expected_parts=len(sd._parts),
        model_name=audit.root_submodel,
        include_connectors=include_connectors,
    )
    pending = root / (ident + ".request.json")
    temporary = pending.with_suffix(".tmp")
    temporary.write_text(json.dumps(request), encoding="utf8")
    os.replace(temporary, pending)
    output = root / (ident + ".result.json")
    deadline = time.monotonic() + timeout
    while not output.exists():
        if time.monotonic() >= deadline:
            pending.unlink(missing_ok=True)
            raise TimeoutError(
                "Native Studio check timed out; model must not be accepted"
            )
        time.sleep(0.1)
    result = json.loads(output.read_text(encoding="utf8"))
    if not result.get("ok"):
        raise RuntimeError(
            "Native Studio check failed: " + result.get("error", "unknown error")
        )
    if (
        result.get("request_id") != ident
        or result.get("audit_sha256") != digest
        or result.get("parts_checked") != len(sd._parts)
    ):
        raise RuntimeError("Native Studio response does not match the requested model")
    counts = [
        result.get(k)
        for k in ("warnings", "cautions", "stability_issues", "detached_sections")
    ]
    if any(type(n) is not int or n < 0 for n in counts):
        raise RuntimeError("Invalid native Studio counters")
    if result.get("coordinate_system") != "LDraw_LDU" or not isinstance(
        result.get("unmodelled_parts"), list
    ):
        raise RuntimeError(
            "Incompatible native worker: missing coordinate/physics coverage metadata"
        )
    return {
        **result,
        "status": (
            "unverified_physics"
            if result.get("unmodelled_parts")
            else "issues_found" if any(counts) else "clear"
        ),
        "evidence": str(output),
    }
