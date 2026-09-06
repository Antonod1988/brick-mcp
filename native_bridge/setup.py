"""Set up the isolated Windows Studio worker; do not modify installed Studio DLLs."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "5.4.23.5"
SHA256 = "82f9878551030f54657792c0740d9d51a09500eeae1fba21106b0c441e6732c4"
URL = f"https://github.com/BepInEx/BepInEx/releases/download/v{VERSION}/BepInEx_win_x64_{VERSION}.zip"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--studio", default=r"D:\Progs\Studio 2.0")
    studio = Path(parser.parse_args().studio).resolve()
    for name in (
        "Studio.exe",
        "UnityPlayer.dll",
        "Studio_Data/Managed/Studio.dll",
        "version.txt",
    ):
        if not (studio / name).is_file():
            raise FileNotFoundError(studio / name)
    worker = ROOT / ".cache/studio-worker"
    worker.mkdir(parents=True, exist_ok=True)
    package = ROOT / f".cache/BepInEx_win_x64_{VERSION}.zip"
    if not package.exists():
        urlretrieve(URL, package)
    if hashlib.sha256(package.read_bytes()).hexdigest() != SHA256:
        raise ValueError("BepInEx archive checksum mismatch")
    with ZipFile(package) as archive:
        for entry in archive.infolist():
            target = worker / entry.filename
            if not target.resolve().is_relative_to(worker.resolve()):
                raise ValueError("Unsafe archive path")
            if not target.exists():
                archive.extract(entry, worker)
    for source, target in [
        ("Studio.exe", "StudioWorker.exe"),
        ("UnityPlayer.dll", "UnityPlayer.dll"),
        ("version.txt", "version.txt"),
        ("testServer2.txt", "testServer2.txt"),
    ]:
        if not (worker / target).exists():
            shutil.copyfile(studio / source, worker / target)
    for source in ("Studio_Data", "MonoBleedingEdge", "ldraw", "data", "Licenses"):
        target = worker / ("StudioWorker_Data" if source == "Studio_Data" else source)
        if target.exists():
            if target.resolve() != (studio / source).resolve():
                raise ValueError(f"Existing worker link points elsewhere: {target}")
        else:
            quote = lambda p: "'" + str(p).replace("'", "''") + "'"
            subprocess.run(
                [
                    shutil.which("pwsh") or "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    f"New-Item -ItemType Junction -Path {quote(target)} -Target {quote(studio/source)} | Out-Null",
                ],
                check=True,
            )
    (worker / "BepInEx/plugins").mkdir(exist_ok=True)
    (worker / "jobs").mkdir(exist_ok=True)
    (worker / "source.json").write_text(
        json.dumps(
            {
                "studio_dir": str(studio),
                "bepinex_version": VERSION,
                "bepinex_sha256": SHA256,
                "studio_assembly_sha256": hashlib.sha256(
                    (studio / "Studio_Data/Managed/Studio.dll").read_bytes()
                ).hexdigest(),
            },
            indent=2,
        ),
        encoding="utf8",
    )
    sys.path.insert(0, str(ROOT / "src"))
    from brick_mcp.model import StudioProject
    from brick_mcp.io_file import write_io_file

    bootstrap = worker / "jobs/bootstrap.io"
    if not bootstrap.exists():
        project = StudioProject.new("bridge-bootstrap")
        project.add_part(None, "3001", 4, 0, 0, 0)
        write_io_file(
            str(bootstrap), project.to_ldraw_text(), {}, project.to_v2_ldraw_text()
        )
    print("Native Studio worker configured:", worker)


if __name__ == "__main__":
    main()
