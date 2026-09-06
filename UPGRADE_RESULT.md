# Brick MCP 0.2 acceptance — 2026-09-06

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
