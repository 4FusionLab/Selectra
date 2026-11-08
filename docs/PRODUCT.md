# Selectra: selection by example

[Русская версия](PRODUCT.ru.md)

## Problem

The user shows what they consider similar, and Selectra proposes a selection. The main entry point is `Select Similar` in the right-click menu. A separate `Select Chain` finds closed edge loops and wall chains. The user should not have to begin by choosing a technical metric.

**Search scope clarified by the user on 25 October 2026:** This Body, This Component (default), All Components. This Component includes the selected instance's nested hierarchy; All Components includes the entire visible assembly. Examples and exclusions lie within the selected scope. Scope is not expanded implicitly; switching it is visible in the dialog. Canonical semantics: [UX.md](UX.md).

For the current workflow and controls see [UX.md](UX.md). For the target intent-inference model see [INTENT_MODEL.md](INTENT_MODEL.md). PgUp/PgDown control ranked similarity; graph adjacency remains a separate operation.

## Main workflow

1. Select one or more edges or faces from one body.
2. Right-click → `Select Similar`. Geometry is read after starting the command, not every time the menu opens.
3. Immediately see the best proposed set and its count. Examples remain in the set. If ambiguous, show a brief explanation.
4. Press `OK` to obtain an ordinary Fusion selection and continue working, for example by starting Fillet. `Cancel` restores the original selection if the context is unchanged.
5. If the result is wrong, refine it with an example or exclusion. The native dialog has Examples and Exclude; refinement recalculates ranking and resets the manual range.

The main area contains the Similarity slider, which controls the same range as PgUp/PgDown. `Refine` is collapsed and contains optional Match and Reset Range. Automatic ranking defaults to a 1% dimensional and 2° angular tolerance. Numeric distance is not presented as an intent probability.

## How intent is inferred

All entities of the selected type in the source body receive a continuous geometric similarity score. Shared example features determine weights; features that differ cease to be mandatory. Sets with equal scores are included as a whole. The original separate-hypothesis kernel is retained for explanations and comparison; main range control uses a shared ranking rather than switching disconnected sets.

Examples:

- Two straight edges of different lengths but the same direction → length is excluded as a feature, leaving parallel edges.
- Two edges of the same length with different directions → direction no longer restricts the set.
- Two cylindrical faces with the same radius and different areas → find the same radius, not the same area.
- Two disconnected planar faces of different sizes with complete contours → find the union of verified analogues of each example; a shared normal does not replace shape.

A straight edge's direction is an axis: reversing its parameterization by 180° changes nothing. Automatic compares the axis of a planar normal; explicit Orientation uses a directed vector and distinguishes opposite sides. A single arbitrary normal does not describe the complete direction of a curved surface.

If examples have no stable common feature, the tool reports this. It must not silently select the entire body. For disconnected planar examples with complete contours, the union of verified shape-and-size families is supported. Connected examples can still describe a repeated feature, while opposite sides can describe a wall family. Connected groups with cylindrical and NURBS faces are additionally checked by surface triangulation and relative arrangement. Other geometry types use available shared features.

## Scenario catalog

| Example | Intended meaning | Features and ambiguity | Stage |
| --- | --- | --- | --- |
| Straight edge | Same length; parallel; or both | Length and axis. A second example distinguishes intent | Kernel spike |
| Circular edge | Edges of the same radius | Curve type + radius; distinguish a full circle and an arc | Kernel spike |
| Arc | Same radius, or radius and length | Do not call every circle a hole | Kernel spike |
| Planar face | Same dimensions/boundary or orientation | Area, perimeter, edge/loop counts, normal; not proof of congruence | Kernel spike |
| Cylindrical face | Same radius, sometimes area | Holes and external shafts are not yet distinguished | Kernel spike |
| Through or blind hole | All holes of the same diameter/type | Internal orientation, axis, loops, bottom, adjacency | Semantics after CAD spike |
| Fillet | All fillets of the same radius | Cylinder/torus/freeform, neighboring faces, convexity | After basic MVP |
| Chamfer | All chamfers of the same width/angle | Geometry and adjacency; area alone is insufficient | After basic MVP |
| Edge chain | Tangentially connected or equivalent chains | Adjacency graph; distinguish from native Tangent Chain | After basic MVP |
| Pocket/boss | Similar face groups | Topological region rather than individual faces | Separate stage |
| STEP import | Repeated features without history | Geometry and topology; Hole/Pattern history is optional | MVP CAD corpus |
| Freeform surface | Repeated shape regions | Curvature, orientation and boundary sampling; area is only a coarse filter | Research |

Mesh, T-Spline, and sketch entities are outside the initial BRep MVP. For connected groups of curved BRep faces, a discrete shape check under one shared transformation is supported. Individual curved faces retain simple numerical comparisons; exact analytical recognition of arbitrary NURBS is not claimed.

## Engineering decisions informed by Perfora

The kernel receives immutable snapshots only; reordering examples does not change the result. The Fusion adapter preserves the original context. No attributes are written to edges or faces. The model is not rebuilt and temporary CAD bodies are not created.

Use inexpensive analytical features first. Add topology and curvature refinement only where it reduces false matches. Prototype limits: up to 10,000 body entities and a soft two-second reading budget. Checking the budget between API calls cannot interrupt one long call; it prevents traversal from continuing, but does not guarantee UI latency. Large-scale highlighting needs separate measurement.

Implement the first intent model locally and deterministically. An LLM is not needed to compare BRep. Adaptation to user habits may be studied later using explicit corrections, without substituting it for geometric checks.

## Closed chains

Select Chain separates topology from similarity. One or more examples start a search for the nearest closed contour passing through them. Chain across contact is enabled by default and permits transitions across a full exact body contact. PgUp/PgDown and =/- switch individual contour options, replacing the previous one. Edges and faces have separate semantics described in UX. Bodies, geometry and the timeline do not change.

Select Chain clarification: every contour at every level passes through all selected examples. PgUp/PgDown and =/- switch valid traversals through them without accumulation. Searching neighboring holes, remote contours, or graph expansion are not part of Select Chain. Plane affects only the ordering of already valid contours.

Cross-contact search preserves original contours of individual bodies and adds contours across exact contact. Temporary seam removal during Boolean Union does not mean contours along the original split line disappear from the selection. This applies to edges and wall chains alike.

For edges, the catalog also includes boundaries of intermediate connected parts of a smooth region. An interior seam of the complete region can remain a boundary of one of its parts and belong to a requested contour. These additional options follow earlier contours in the same plane class; each must still contain every example. Enumeration is bounded by topology and time budgets; exceeding a budget explicitly cancels the result.

For faces, closed strips of one body with two simple boundaries and a cycle of cross seams are also recognized. A narrow strip takes priority; width relative to boundary length is an ordering heuristic, not proof of intent. Previously available traversals remain options. This check does not yet construct strips across the contact of multiple bodies.
