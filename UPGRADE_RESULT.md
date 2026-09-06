# Brick MCP 0.3 native Studio checks — 2026-09-06

Implemented and exercised direct calls to Studio's StabilitySimulator through a
dedicated local worker. No Computer Use is required. apply_step checks each prefix
before commit and rechecks affected parents; native failures roll back. Atomic
step replacement, explicit soft-caution handling, missing-canvas-physics reporting,
native connector inspection and prototype cleanup are available. Fresh stdio
exposes 34 tools. Existing app MCP connections need reconnecting for new schemas.

Verification: 231 unit/regression tests; live native two-brick positive/negative
checks; real stdio step acceptance and rollback; IO/MPD report persistence; and a
cold-worker auto-start followed by the complete stdio/PNG workflow. Latest live
workflow artifact: `output/workflow-check-blnxzvlz`. Unit tests stub the process
transport; the live checks use installed Studio 2.26.8 (1).

The repaired pirate ship is in `output/pirate-ship-checked`: 442 rigid parts / 77
steps, and a separate 450-part / 85-step visual version with eight fabric sails.
Rigid checks show zero red warnings, zero detached sections and zero instability,
with 35 explicitly retained soft cautions. Fabric remains unverified; the display
instruction export is a draft. Final reports and BOMs are alongside both models.

## Previous 0.2 acceptance

Completed the agreed instruction workflow upgrade. The configured stdio server
exposes 31 tools. The runtime remains local; no paid AI provider calls were used.

## Verification

- 217 unit/regression tests passed.
- Real stdio acceptance: `output/workflow-check-434asway/result.json`.
- Cottage: 220 physical parts, 20 main steps, 47 illustrated steps across the
  9 used assemblies/variants. The unused Flower template remains for further edits.
- All model/assembly sequences returned `passed` under the documented ordinary
  stud/receiver and vertical-insertion checks.
- IO/MPD round trips preserve native step descriptions, colors, submodels and BOM.
- All 47 exported PNGs exist. Contact-sheet review plus individual highlighted
  frames verified framing and new-part visibility, including gray-on-gray pieces.
- Studio 2.26.8_1 inspection confirmed the named main steps and the final distinct
  flower colors with green stems. Computer Use was limited to interoperability
  checks; construction and repairs were performed through MCP.

## User artifacts

- `output/cottage-instructions-43l434w3/final-instructions/model.io`
- `output/cottage-instructions-43l434w3/final-instructions/model.mpd`
- `output/cottage-instructions-43l434w3/final-instructions/instructions.html`
- `output/cottage-instructions-43l434w3/final-instructions/instructions.json`
- `output/cottage-instructions-43l434w3/final-validation.json`

## Defects found and resolved during acceptance

The old dimensions table mislabeled a helmet as a plate. Aliases produced false
dimensions. An actual half-stud flowerbed alignment error passed old collision
checks but was rejected by the new connector checks. It was repaired in the
MCP checkpoint and the build resumed without repeating completed steps.

POV-Ray's native Windows startup stalled during testing; the default renderer is
now a local triangle z-buffer. NumPy is initialized before MCP worker threads to
avoid a native import deadlock. Mixed image tools explicitly disable automatic
output-schema inference so valid PNG responses pass FastMCP's validation.

Studio required explicit colored submodel copies and unique clone headers for
the flower variants. The corrected behavior is covered by a saved-prototype
round-trip regression and was verified in Studio.

## Limits

Complex clips/pins/hinges and unusual orientations are explicitly unverified.
Conservative bounds for irregular parts are not exact collision proofs. No
strength/clutch-force simulation or automatic Studio scene refresh is claimed.
Software instruction previews render transparent pieces as opaque. See
`LOCAL_SETUP.md` for commands, configuration and recovery.
