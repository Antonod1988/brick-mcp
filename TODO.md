# BrickLink Studio MCP — Technical Research

# UPDATE!

- ./example.io added with ./tmp as unpacked version

## 1. The .io File Format

### Structure

The `.io` file is a **ZIP archive**. (documented on the LDraw.org wiki and in multiple community discussions). Inside the ZIP, there are approximately six files:

| File | Purpose |
|------|---------|
| `model.ldr` | The core model data in standard **LDraw format** |
| Scene/camera data | Floor, background, lighting, camera views |
| Thumbnail(s) | Preview images of the model |
| Metadata | Project settings and rendering configuration |

The model data is the key file — it uses the open LDraw format, which is the real interchange layer we need to parse.

### Implications for the MCP

- **Reading**: Unzip with the known password → extract `model.ldr` → parse LDraw.
- **Writing**: Modify `model.ldr` → repackage into a password-protected ZIP → save as `.io`.
- **Libraries**: Any ZIP library with password support works (`adm-zip`, `archiver` for Node.js; Python's `zipfile`).

---

## 2. The LDraw File Format (Core Data Format)

LDraw is the actual data format that matters. It is a **plain-text, line-based format** dating from 1995, with a well-documented specification maintained at ldraw.org.

### Line Types

Each line starts with a command number:

| Line Type | Meaning | Format |
|-----------|---------|--------|
| **0** | Comment / META command | `0 <comment>` or `0 !<META> <args>` |
| **1** | Sub-file reference (part placement) | `1 <color> <x> <y> <z> <a> <b> <c> <d> <e> <f> <g> <h> <i> <file>` |
| **2** | Line segment | `2 <color> <x1> <y1> <z1> <x2> <y2> <z2>` |
| **3** | Triangle | `3 <color> <x1> <y1> <z1> <x2> <y2> <z2> <x3> <y3> <z3>` |
| **4** | Quadrilateral | `4 <color> <4 vertices>` |
| **5** | Optional/conditional line | `5 <color> <2 vertices> <2 control points>` |

### Line Type 1 — The Key Data

Line type 1 is how parts are placed in a model. The 9 numbers after x/y/z form a **3×3 transformation matrix** (rotation + scale):

```
1 <color> <x> <y> <z> <a> <b> <c> <d> <e> <f> <g> <h> <i> <part_file.dat>
```

Where `[a b c / d e f / g h i]` is the rotation matrix and `<x y z>` is the position. The part file is referenced from the LDraw parts library (e.g., `3001.dat` for a 2×4 brick).

### META Commands (Line Type 0)

Key meta commands for model structure:

| Command | Purpose |
|---------|---------|
| `0 STEP` | Step boundary (building instruction step) |
| `0 FILE <name>` | Start of a sub-file in MPD (multi-part document) |
| `0 NOFILE` | End of a sub-file block |
| `0 !COLOUR` | Color definition |
| `0 BFC CERTIFY CCW/CW` | Back-face culling winding order |
| `0 !CATEGORY` | Part category |
| `0 !KEYWORDS` | Search keywords |

### MPD (Multi-Part Document)

Models with submodels use MPD structure — multiple `0 FILE` blocks concatenated in one file. The first block is the main model; others are sub-assemblies referenced by line type 1.

### Coordinate System & Units (LDU)

The LDraw Unit (LDU) system is integer-based, which is one of its great strengths:

| Measurement | LDU | mm |
|-------------|-----|-----|
| 1 stud width | 20 | 8.0 |
| 1 plate height | 8 | 3.2 |
| 1 brick height | 24 | 9.6 |
| 1 cm | 25 | 10.0 |
| 1 inch | 64 | 25.4 |
| Stud diameter | 12 | 4.8 |
| Stud height | 4 | ~1.7 |

**Key ratios**: 1 brick = 3 plates. Width-to-height ratio is 5:6 (20 LDU wide vs 24 LDU tall), which is why LEGO bricks are not square. 5 plates = 2 studs width (40 LDU).

The Y-axis is inverted (negative Y is up) in LDraw convention.

---

## 3. Existing Libraries & Tools

### JavaScript / TypeScript (for Node.js MCP server)

| Library | Status | Notes |
|---------|--------|-------|
| **`ldraw` (npm)** | Stable but old (2015) | Basic parser: `loadModel()`, `parseModel()`, `parseColors()`. Returns command arrays. No write support. |
| **Three.js `LDrawLoader`** | Active, well-maintained | Full LDraw parser + 3D renderer. Handles materials, BFC, steps. Browser-focused but the parser logic is reusable. Located in `three/addons/loaders/LDrawLoader.js`. |
| **`brick-viewer`** | Demo web component | Wraps Three.js LDrawLoader as a `<brick-viewer>` custom element. Good reference for integration patterns. |
| **`adm-zip` / `jszip`** | Stable | ZIP handling with password support for `.io` extraction/creation. |

### Python

| Library | Status | Notes |
|---------|--------|-------|
| **`pyldraw` (michaelgale)** | Active, Python 3.9+ | Full read/write of LDraw files. `LdrColour`, model manipulation, clean API. Best Python option. |
| **`python-ldraw` (rienafairefr)** | Maintained | Import parts by Python name, auto-generates library from `complete.zip`. GPL licensed. |
| **`LDRParser`** | Basic | Recursive parser outputting JSON/dict. Good reference for understanding format but limited. |

### Rust

| Library | Status | Notes |
|---------|--------|-------|
| **`weldr`** | Active | LDraw parser using `nom` combinator library. Converts to glTF 2.0. Produces `Command` enum AST. Clean, typed API. MIT license. |

### C/C++

| Library | Status | Notes |
|---------|--------|-------|
| **`ldrawloader` (pixeljetstream)** | Active (v0.3, 2024) | Full loader with render-part building, T-junction fixing, smoothing, chamfer. Very low-level. |
| **LDView** | Mature, open source | Full OpenGL viewer with command-line snapshot rendering. Supports `-SaveSnapshot=file.png`, custom resolution, zoom-to-fit. Ideal for headless rendering if available on the server. |
| **LPub3D** | Mature | Building instruction editor. Bundles LDView, LDGLite, POV-Ray. Can generate instruction step images. |

### Key Parts Database

Studio's own part database is `StudioPartDefinition2.txt` — a tab-separated table mapping BrickLink part IDs to LDraw part numbers, categories, dimensions, and color availability. Located at `C:\Program Files\Studio 2.0\data\` on Windows installations.

The LDraw parts library (`complete.zip` from ldraw.org) contains ~16,500 unique part geometries as of March 2026.

---

## 4. Data Structures

### In-Memory Model (Recommended)

```typescript
// Core model representation
interface StudioProject {
  filename: string;
  rawZipEntries: Map<string, Buffer>;  // preserve non-model files for round-tripping
  model: LDrawModel;
}

interface LDrawModel {
  header: ModelHeader;
  submodels: Map<string, Submodel>;  // name → submodel
  rootModelName: string;
}

interface ModelHeader {
  title: string;
  author?: string;
  license?: string;
  ldrawOrg?: string;
}

interface Submodel {
  name: string;
  commands: LDrawCommand[];  // raw parsed commands in order
  parts: PartInstance[];      // extracted from line type 1 commands
  steps: StepBoundary[];      // indices into commands array
}

interface PartInstance {
  id: string;                          // generated unique ID
  partNumber: string;                  // e.g., "3001.dat"
  color: number;                       // LDraw color code
  position: Vector3;                   // x, y, z in LDU
  rotation: Matrix3x3;                // 3×3 rotation matrix (9 values)
  commandIndex: number;                // position in parent's commands array
}

interface StepBoundary {
  commandIndex: number;                // index of the 0 STEP command
  partsBefore: string[];               // part IDs visible up to this step
}

// LDraw command union type
type LDrawCommand =
  | { type: 'comment'; text: string }
  | { type: 'meta'; command: string; args: string }
  | { type: 'partRef'; color: number; position: Vector3; rotation: Matrix3x3; file: string }
  | { type: 'line'; color: number; vertices: [Vector3, Vector3] }
  | { type: 'triangle'; color: number; vertices: [Vector3, Vector3, Vector3] }
  | { type: 'quad'; color: number; vertices: [Vector3, Vector3, Vector3, Vector3] }
  | { type: 'optLine'; color: number; vertices: [Vector3, Vector3]; control: [Vector3, Vector3] }
  | { type: 'step' }
  | { type: 'file'; name: string }
  | { type: 'nofile' };

interface Vector3 { x: number; y: number; z: number; }

// 3×3 rotation matrix stored as row-major array
type Matrix3x3 = [number, number, number,
                   number, number, number,
                   number, number, number];
```

### Parts Lookup Index

```typescript
interface PartInfo {
  ldrawId: string;           // e.g., "3001"
  bricklinkId?: string;      // may differ from LDraw ID
  name: string;              // "Brick 2 x 4"
  category: string;          // "Brick"
  dimensions: {              // in studs
    width: number;
    length: number;
    height: number;          // in brick units (1 brick = 1, 1 plate = 0.33)
  };
  boundingBox: {             // in LDU
    min: Vector3;
    max: Vector3;
  };
  connectionPoints?: ConnectionPoint[];
}

interface ConnectionPoint {
  type: 'stud' | 'antistud' | 'pin' | 'axle' | 'clip' | 'bar';
  position: Vector3;         // relative to part origin
  direction: Vector3;        // normal direction
}
```

### Color Database

```typescript
interface LDrawColor {
  code: number;              // LDraw color code (e.g., 0 = Black)
  name: string;              // "Black"
  hex: string;               // "#05131D"
  edge: string;              // "#595959"
  material: 'SOLID' | 'TRANSPARENT' | 'METALLIC' | 'PEARL' | 'RUBBER' | 'CHROME';
  legoId?: number;           // LEGO element color ID
  bricklinkId?: number;      // BrickLink color ID
}
```

Colors are defined in `LDConfig.ldr` in the LDraw library. Direct colors (inline RGB) use the format `0x2RRGGBB`.

---

## 5. Algorithms

### 5.1 LDraw Parser

The parser is line-based and straightforward:

1. Split file into lines
2. For each line, read the first token (line type number)
3. Parse remaining tokens based on line type
4. Handle MPD: when `0 FILE` is encountered, start a new submodel block

The tricky parts are handling nested sub-file references (line type 1 can reference other files that contain more line type 1 references) and applying the transformation matrices recursively.

**Matrix composition for nested parts**: When part A at transform `M_A` references part B at transform `M_B`, the world transform of B is: `M_world = M_A × M_B`.

### 5.2 Bounding Box Calculation

For model-level bounding boxes, compute the axis-aligned bounding box (AABB) of all parts:

1. For each part instance, look up its part geometry bounding box
2. Transform the 8 corners of the bounding box by the part's transform matrix
3. Expand the model AABB to include all transformed corners

For a lightweight index without full part geometry, use the known dimensions from the parts database and approximate each part as a box at its position.

### 5.3 Spatial Indexing (for Collision & Proximity)

For models with hundreds/thousands of parts, spatial queries benefit from acceleration structures:

- **Uniform Grid / Spatial Hash**: Best for LEGO models because parts are distributed on a regular grid. Divide space into cells of 20×24×20 LDU (1 stud × 1 brick × 1 stud). O(1) average lookup. Simple to implement. Good for "which parts are near position X?"

- **Octree**: Better for models with varying part density. Recursively subdivide space. Good for models spanning large areas (like cities) with dense clusters.

- **R-tree / BVH**: Best for arbitrary range queries and ray-casting. Overkill for most MCP operations but useful if doing rendering or complex intersection tests.

**Recommendation**: Start with a spatial hash map. Keys are `(floor(x/20), floor(y/8), floor(z/20))` grid cells. Each cell stores a list of part instance IDs whose bounding boxes overlap that cell.

### 5.4 Connectivity Analysis

LEGO connectivity at the stud level:

1. **Stud-to-antistud**: The primary connection. A stud at position `(sx, sy, sz)` connects to an antistud at position `(ax, ay, az)` when they are within tolerance (sy - ay ≈ plate_height and sx ≈ ax, sz ≈ az within stud pitch).

2. **Grid-based approach**: Since most standard connections happen on the stud grid (20 LDU pitch horizontally, 8 or 24 LDU vertically), discretize to a grid and check which parts have studs/antistuds at adjacent grid positions.

3. **Connection types to model**:
   - Stud-on-top (standard vertical stacking)
   - SNOT (studs not on top — sideways connections via headlight bricks, brackets)
   - Technic (pins, axles, pin holes)
   - Clip-and-bar connections

**Phase 1 approach**: Only check stud-on-top connections. For each part, compute stud positions (top) and antistud positions (bottom) from known part dimensions. Two parts are connected if any stud aligns with an antistud.

### 5.5 Collision Detection

Lightweight approach for the MCP (not pixel-perfect):

1. Compute oriented bounding box (OBB) for each part
2. Use spatial hash for broad phase (find candidate pairs)
3. OBB-OBB intersection test for narrow phase
4. Parts that overlap but are at legal connection positions (stud-in-antistud) are not collisions

Full collision detection (as Studio does it) requires the actual part mesh geometry, which is much more expensive.

### 5.6 Step Sequencing / Instruction Generation

Building steps are already encoded in the LDraw file via `0 STEP` commands. To validate or improve step ordering:

- **Gravity check**: Each step's newly added parts should rest on previously placed parts (connected below).
- **Accessibility check**: Parts added in a step shouldn't require passing through existing parts.
- **Assembly-by-disassembly**: A well-known heuristic — simulate removing parts one by one; reverse the order for build steps.

### 5.7 Bill of Materials

Straightforward aggregation:

1. Iterate all `PartInstance` objects
2. Group by `(partNumber, color)` tuple
3. Count quantities
4. Map LDraw part numbers to BrickLink IDs using the parts database
5. Map LDraw colors to BrickLink colors

---

## 6. Rendering Strategy

### Option A: Three.js LDrawLoader (Headless)

Use Three.js server-side with `headless-gl` for WebGL rendering:

- **Pros**: Full LDraw rendering including materials, BFC, conditional lines. Same renderer used by many LDraw web viewers.
- **Cons**: Headless GL can be finicky (requires mesa/osmesa on Linux, `headless-gl` npm package). Recent Three.js versions may need `navigator` polyfill.
- **Setup**: `gl` (headless-gl) + `three` + `sharp` (for PNG output).

### Option B: LDView CLI

LDView has command-line rendering built in:

```bash
LDView model.ldr -SaveSnapshot=output.png -SaveWidth=1024 -SaveHeight=768 \
  -SaveZoomToFit=1 -AutoCrop=1 -SaveAlpha=1
```

- **Pros**: Battle-tested, high-quality output, supports up to 9999×9999px, alpha transparency.
- **Cons**: Requires LDView installed on the server. Uses OSMesa for software rendering on headless systems.

### Option C: POV-Ray Pipeline

Convert LDraw → POV-Ray scene → render with POV-Ray:

- **Pros**: Photorealistic output. LPub3D and Studio both use this path.
- **Cons**: Slow. Multi-step pipeline. Overkill for inspection thumbnails.

### Option D: SVG Orthographic Projection (No GPU Required)

For a lightweight "inspection" view that doesn't require any GPU:

1. Parse all parts and their bounding boxes
2. Project to 2D using an isometric or orthographic camera matrix
3. Draw rectangles/outlines as SVG
4. Color-code by part color

- **Pros**: Zero dependencies, runs anywhere, fast.
- **Cons**: No real 3D, no part detail — more of a "block diagram" than a render.

### Recommendation

Support a hierarchy: try LDView CLI first (best quality), fall back to headless Three.js, fall back to SVG schematic. Make the rendering strategy configurable.

---

## 7. Recommended Tech Stack

### Primary: TypeScript + Node.js

| Component | Library | Purpose |
|-----------|---------|---------|
| MCP server | `@modelcontextprotocol/sdk` | MCP protocol implementation |
| ZIP handling | `adm-zip` | Password-protected ZIP read/write for .io files |
| LDraw parsing | **Custom parser** (referencing Three.js LDrawLoader logic) | Full LDraw format support including MPD, BFC, STEP |
| Color database | `LDConfig.ldr` parser | Map color codes to names, hex, BrickLink IDs |
| Parts database | Bundled JSON index (~2MB) | Generated from LDraw `parts.lst` + BrickLink catalog |
| Spatial index | Custom spatial hash | Collision/proximity queries |
| 3D math | `gl-matrix` or custom | Vector3, Matrix4 operations |
| Rendering (primary) | LDView CLI | High-quality snapshots |
| Rendering (fallback) | Three.js + `headless-gl` | Server-side WebGL |
| Rendering (minimal) | Custom SVG generator | No-dependency schematic views |

### Why Custom Parser Over Existing npm `ldraw`?

The existing `ldraw` npm package is from 2015 and lacks: MPD support, BFC handling, meta command parsing, write/serialization, and TypeScript types. Three.js's `LDrawLoader` has excellent parsing but is coupled to Three.js's object model. The best approach is a standalone parser inspired by `LDrawLoader`'s parsing logic but producing our own typed AST.

---

## 8. Key Design Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Language | TypeScript | MCP SDK is JS-native; type safety for complex data structures |
| .io extraction | `adm-zip` with known password | Simple, well-tested |
| Primary data format | LDraw AST | The .io format is just a ZIP wrapper around LDraw |
| Parser strategy | Custom line-by-line | Format is simple enough; existing libs are outdated or coupled |
| Spatial index | Spatial hash (20×8×20 LDU cells) | Matches LEGO grid; O(1) average; simple |
| Connectivity | Grid-based stud matching (Phase 1) | Covers ~90% of connections; defer Technic/SNOT to Phase 2 |
| Collision | OBB broad phase + part-specific narrow phase | Good enough for validation without full mesh geometry |
| Rendering | LDView CLI → Three.js headless → SVG fallback | Progressive capability based on server environment |
| Parts database | Pre-built JSON from LDraw + BrickLink mapping | Fast lookup, no runtime dependency on external databases |
| State management | In-memory model, mutation + save | MCP server holds open model; explicit save step |
| Round-tripping | Preserve non-model ZIP entries | Don't lose scene/camera/thumbnail data when editing model.ldr |

---

## 9. References

- **LDraw File Format Spec**: https://www.ldraw.org/article/218.html
- **LDraw MPD Spec**: https://www.ldraw.org/article/47.html
- **LDraw Color Spec**: LDConfig.ldr in parts library
- **LDraw Parts Library**: https://library.ldraw.org/library/updates/complete.zip
- **Three.js LDrawLoader**: https://threejs.org/docs/pages/LDrawLoader.html
- **LDView (CLI renderer)**: https://ldview.sourceforge.net/
- **weldr (Rust LDraw parser)**: https://github.com/djeedai/weldr
- **pyldraw (Python)**: https://github.com/michaelgale/pyldraw
- **BrickLink Studio Wikipedia**: https://en.wikipedia.org/wiki/BrickLink_Studio
- **LDraw Wiki on Studio**: https://wiki.ldraw.org/wiki/Category:BrickLink_Studio
- **LDU explainer**: https://bricknerd.com/home/ldu-and-you-the-oldest-new-lego-measurement-unit-2-9-23
- **Brick dimensions**: https://notebook.zoeblade.com/Lego_brick_dimensions.html
