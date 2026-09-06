# Native Studio bridge

The MCP calls Studio's own `StabilitySimulator.SimulateStability(0)` and `(1)` in a separate Unity process. It does not click the UI and does not substitute a homemade strength calculation. Tested with installed Studio 2.26.8 (1), Unity 2022.3.62f3. Private bindings can change in a future Studio update; binding/load/time-out failures are errors, never successful checks.

`setup.py` downloads the pinned [BepInEx 5.4.23.5 release](https://github.com/BepInEx/BepInEx/releases/tag/v5.4.23.5), verifies the archive checksum and creates an isolated worker. Installed Studio binaries are only read; Unity libraries/catalogue are shared through directory junctions. The worker uses its own recovery/cache profile. Development inspection files are not distributed. [BepInEx documentation](https://docs.bepinex.dev/master/articles/user_guide/installation/unity_mono.html).

From the repository on Windows:

```powershell
.\.venv\Scripts\python.exe native_bridge\setup.py --studio 'D:\Progs\Studio 2.0'
.\native_bridge\start.ps1
.\.venv\Scripts\python.exe native_bridge\probe.py
```

The default worker auto-starts on the first native check. `BRICK_STUDIO_BRIDGE_DIR` optionally selects an already running custom worker's jobs folder. `start.ps1` restarts only the PID whose executable matches this worker; it does not stop the user's Studio. Idle rendering is capped at 5 FPS. No network listener or remote-control endpoint is created.

Requests and results have unique IDs and input SHA-256 hashes. Loading must finish with the expected unique model name and exact part count. The bridge waits for both native asynchronous calculations and returns counters, problem-part coordinates in LDraw LDU, missing-physics parts, engine DLL hash and evidence path. Native data and current model/step fingerprints are preserved in IO/MPD comments; they become stale when the relevant content changes.

Use `apply_step` for construction. Each step is checked before save/commit; replacement and submodel edits also recheck later prefixes and affected parents. `check_studio_stability` checks existing steps; `inspect_studio_connectors` reads actual connector data. `allow_cautions` accepts only soft cautions explicitly. It cannot bypass red warnings, detachment or instability. Fabric sails without native connectors can be added for display with `allow_unverified_canvas`; both full and rigid-subset calculations run, and the full result remains unverified. Such instruction exports require `draft=True`.

The unit suite isolates the transport; `probe.py` and the real stdio workflow check exercise the installed engine. The native test is conservative and is not a physical safety certificate. Saved screenshots/manual counters are no longer used as an automatic verification substitute. After changing server code, an existing Codex MCP connection needs reconnecting to discover new tools; a fresh stdio client uses the updated code immediately.
