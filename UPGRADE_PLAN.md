# Instruction workflow upgrade

User scope: complete the six agreed MCP improvements; use Computer Use only
when needed to verify Studio-specific interoperability.

- [x] Canonical aliases; geometry-derived bounds; reject invalid/unknown inputs.
- [x] Transactional steps, rollback and safe file replacement; atomic batch option.
- [x] Named/editable steps, insertion, splitting, ordering and part movement.
- [x] Submodel creation/grouping/placement and recursive BOM/validation/rendering.
- [x] Stud/receiver attachment graph, unsupported parts, insertion access checks.
- [x] Real-geometry render_model/render_step, new-part highlighting, exports.
- [x] Rebuild cottage in assembly order; render/check every step; IO/MPD round trip.
- [x] Tests, real stdio checks, visual QA, setup docs and local commit.

Confirmed limits must remain explicit: conservative boxes for irregular parts,
unknown pin/clip/hinge connectors, no claim of full structural physics or live
Studio synchronization. Dependencies stay locked unless implementation needs one.

Acceptance: 217 unit/regression tests; real stdio MCP check with PNG output;
220-part cottage, 47 illustrated instruction steps across 9 used assemblies.
Studio 2.26.8_1 visual check confirmed 20 named main steps and explicit flower colors.
One unused source Flower template is retained in the model for further editing.
