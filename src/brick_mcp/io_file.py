"""BrickLink Studio .io file read/write.

.io files are ZIP archives (optionally AES-256 encrypted with password "soho0909").
Newer BrickLink Studio versions write plain unencrypted ZIPs.

Archive contents:
  model.ldr    — standard LDraw type-1 format
  modelv2.ldr  — BrickLink Studio v2 format (type-11 lines); this is what
                 Studio actually reads when present — it takes priority
  model2.ldr   — extended/verbose format (not parsed)
  *.png, etc.  — thumbnails, scene, camera data (preserved but not parsed)

Read strategy:  plain ZIP first → AES fallback.
                modelv2.ldr preferred over model.ldr (Studio reads it).
Write strategy: always write as plain (unencrypted) ZIP so Studio can open it.
                Write model.ldr (type-1) + modelv2.ldr (type-11, regenerated).
                Drop old modelv2.ldr / model2.ldr from preserved extras.
"""

from __future__ import annotations

import zipfile as _zipfile

IO_PASSWORD = b"soho0909"

# Files handled explicitly; never copied blindly from raw_zip_entries.
_MANAGED_ENTRIES = {"model.ldr", "modelv2.ldr", "model2.ldr"}


def _open_zip(path: str):
    """Return an open ZipFile-like object.  Tries plain zip first, then AES."""
    zf = None
    try:
        zf = _zipfile.ZipFile(path, "r")
        # Probe: reading the first encrypted entry will raise RuntimeError
        names = zf.namelist()
        if names:
            zf.read(names[0])
        return zf
    except (_zipfile.BadZipFile, RuntimeError):
        if zf is not None:
            zf.close()
    except Exception:
        if zf is not None:
            zf.close()

    try:
        import pyzipper
        zf = pyzipper.AESZipFile(path, "r")
        zf.setpassword(IO_PASSWORD)
        return zf
    except FileNotFoundError:
        raise
    except Exception as e:
        raise RuntimeError(f"Cannot open {path} as plain or AES zip: {e}") from e


def read_io_file(path: str) -> tuple[bytes, dict[str, bytes]]:
    """Open a .io file and return (primary_model_bytes, other_entries).

    ``modelv2.ldr`` is used as the primary model when present (BrickLink Studio
    reads it instead of ``model.ldr``).  The returned ``other_entries`` dict
    excludes ``model.ldr``, ``modelv2.ldr``, and ``model2.ldr`` — those are
    regenerated on write.

    Returns:
        A tuple of (model bytes, dict of other ZIP entries by name).
    Raises:
        FileNotFoundError: if path does not exist.
        KeyError: if neither model.ldr nor modelv2.ldr is found.
        RuntimeError: if the archive cannot be opened.
    """
    with _open_zip(path) as zf:
        names = zf.namelist()
        # modelv2.ldr is the authoritative source; fall back to model.ldr
        if "modelv2.ldr" in names:
            primary_name = "modelv2.ldr"
        elif "model.ldr" in names:
            primary_name = "model.ldr"
        else:
            raise KeyError(
                f"Neither model.ldr nor modelv2.ldr found in {path}. Contents: {names}"
            )
        model_bytes = zf.read(primary_name)
        others = {n: zf.read(n) for n in names if n not in _MANAGED_ENTRIES}

    return model_bytes, others


def write_io_file(
    path: str,
    model_ldr_text: str,
    extra_entries: dict[str, bytes],
    model_v2_text: str = "",
) -> None:
    """Write a plain (unencrypted) .io ZIP file.

    Args:
        path: Destination file path (should end in .io).
        model_ldr_text: Standard LDraw model text (type-1) written as model.ldr.
        extra_entries: Other ZIP entries to preserve (thumbnails, scene data, etc.).
                       Entries whose names are in _MANAGED_ENTRIES are ignored here
                       to avoid writing stale copies.
        model_v2_text: BrickLink Studio v2 format (type-11).  When non-empty,
                       written as modelv2.ldr so Studio picks up the changes.
    """
    with _zipfile.ZipFile(path, "w", compression=_zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("model.ldr", model_ldr_text.encode("utf-8"))
        if model_v2_text:
            zf.writestr("modelv2.ldr", model_v2_text.encode("utf-8"))
        for name, data in extra_entries.items():
            if name not in _MANAGED_ENTRIES:
                zf.writestr(name, data)
