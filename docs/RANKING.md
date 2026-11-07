# Similarity ranking

[Русская версия](RANKING.ru.md)

`ranking.py` processes an immutable BodySnapshot of the explicitly selected scope. All eligible edges or all eligible faces in that snapshot receive a similarity distance; excluded elements also receive a rank but are marked blocked and are not included in the result. When bodies are combined, keys are namespaced; topology and material evidence do not cross body boundaries.

## Features

Automatic ranking of planar faces with complete contours first uses geometric relationships from `intentions.py`. Order: matching trimmed shape and size → direct wall pair of the example → pair of the found analogue → approximate groups. Polygon-loop comparison permits one isometry or reflection, preserving dimensions and relative hole positions; area/perimeter are only an inexpensive preliminary filter. A planar example with a missing contour yields ambiguity and initial level 0.

A wall pair requires opposite outward normals, local offset, overlap of at least half the smaller trimmed region, and thickness no greater than `0.25 * sqrt(min_area)`. This is the current explicit locality heuristic, not a universal law for parts. The adapter checks material within each test trace and absence of intermediate BRep intersections. Sampling across the area remains discrete: no volumetric guarantee for the entire wall is claimed.

Two examples of opposite sides can define a pair family: both shapes, thickness, and one common transformation of the whole pair are required. Two or more connected examples can define a repeated feature: the exact induced graph and common geometry of all faces are checked. An exclusion rejects an entire conflicting feature. Broad parallelism/area hypotheses are permitted only when they explain all examples and separate all exclusions. For disconnected planar examples, the union of verified shape/size families takes priority over broad hypotheses. Each candidate must match the complete contour of at least one example; equal normals are insufficient. Verified connected features and wall pairs retain priority.

The scalar score below is for preliminary filtering, approximate groups, and explicit criteria. It does not by itself verify shape.

Automatic base weights: geometry type 0.8; length/area 1.2; radius 1.6; direction 1.0; normal axis 0.2; perimeter 0.7; side/loop/neighboring-face counts 0.25 each; neighboring-face angle 0.5. Only features available for every example are used. The kernel supports some fields not yet extracted by the native adapter, such as the angle at a shared edge of curved surfaces.

If examples differ on a feature beyond tolerance, automatic mode excludes it from mandatory shared properties. If a feature separates negative examples, its weight increases. Normals are extracted for planar faces and circle/arc planes. For planar faces, Automatic compares the normal axis, so opposite sides of a thin wall are not penalized for 180°. Size and shape outweigh orientation. Explicit Match → Orientation retains the directed normal and distinguishes 0° and 180°. For circles and arcs, explicit Orientation compares the plane axis without normal sign. Straight-line direction is axial: changing parameterization does not change similarity.

Dimensions are compared relative to scale with an absolute lower tolerance. Defaults are 1% relative, 2° angular, 1e-6 cm length, and 1e-8 cm² area. Differences within tolerance become zero. Distances are normalized to [0, 1]; the weighted mean defines ordering, not intent probability.

Scalar automatic distance is checked against all examples. The geometric independent-family hypothesis unions complete matches to each individual example. When one criterion is explicitly chosen, matching any example is allowed, as a union of families. Matching simple numerical features does not prove geometric congruence.

## Ranges

Verified geometric relationships form atomic levels. Approximate planar groups use fixed scalar-distance boundaries 0.02/0.10/0.25/0.50/1.0. Edges use 0/0.005/0.02/0.05/0.10/0.20/0.35/0.60/1.0. This prevents small size variations from requiring a separate PgUp for each entity. Remaining scalar surfaces retain the numerical ties described below.

Equally similar elements are grouped into levels with numerical tolerance 1e-9. Including/removing a level is atomic: identifiers do not split ties. The initial automatic range is the first nonempty candidate group beyond the examples when informative features exist and no indistinguishable exclusion exists. It does not remain at zero because of a fixed numeric threshold. If no eligible candidates exist or feedback conflicts, only examples are retained; the nearest candidate is not called a verified shape analogue.

PgUp adds the next level; PgDown removes the weakest included level. The slider controls the same integer range index. Positive examples are always retained. At maximum, all non-excluded elements of the original type and body are selected. Adjacency does not affect this order.

A new example, exclusion, or criterion recalculates ranks and restores the automatic range. Changing range uses the prepared ranking without rereading BRep. Undo/Redo in the kernel restores refinement state; it does not override Fusion's system Undo.

## Plane ordering

In Automatic, each already constructed geometric level is further divided: in the example plane → in parallel planes → in other planes → with an unknown support plane. Shape and size remain primary: an enlarged coplanar circle does not outrank an exact rotated circle. Each nonempty subclass is a separate PgUp/PgDown or =/- step. Explicit Match criteria do not receive this additional filter.

A circle or arc uses its own curve plane; other edges use available adjacent-face planes. A straight edge can have several: one common support plane is enough. A planar face uses its normal and position. Parallelism is checked by normal axis with 1e-7 rad tolerance; plane coincidence by normal offset with the snapshot's linear tolerance. Reversing a normal does not create a separate step. All data are transformed to instance world coordinates; the camera is not involved.

Multiple explicit examples define the union of their support planes and are always retained. An exclusion of identical shape in another known plane can be explained by plane; an indistinguishable exclusion in the same plane remains ambiguous. Snapshot schema 4 stores support planes; schemas 1–3 remain readable.

## Limits

Scope is This Body / This Component / All Components, defaulting to This Component with the selected instance's complete nested hierarchy. Schema 3 stores the completeness flag for optional wall checks. If that stage is limited, wall pairs are discarded as a whole while the complete entity set and shape comparison remain available; UI reports the limit. Failure of required reading or of the entire scope budget preserves the previous scope without partially applying a new result.

- Contours are extracted with approximation deviation 1e-4 cm; native analysis is limited to 512 points per face and 160 planar faces. Different curve subdivisions into points are not treated as different shapes: after checking topology, support transformations are constructed from integral moments of the outer boundary. Complete polylines are checked in both directions within geometric tolerance; holes are matched bijectively under the same transformation. Segment coverage is proved using convexity of a segment capsule or adaptive subdivision with a Lipschitz distance bound; budget exhaustion yields an incomplete result. Failed alignment can conservatively reject a match. This is not an analytical NURBS recognizer.
- Analysis budgets produce an explicit refusal without partial application. Snapshot schema 2 stores contours and wall pairs; schema 1 remains readable.
- The last included level has a stable 3 px outline; earlier edges retain a 1.5 px outline and faces a 35% fill. Fusion selection is applied only on OK.
- An example and exclusion indistinguishable by available features produce an ambiguity warning; no hidden feature is invented.
- Size families, fillets, and holes are not declared recognized solely from radius or area.
- Real geometry can change through external edits; BodySnapshot is tied to scope and revision, and stale results are not applied.
- Numerical-kernel performance is in [BENCHMARKS.md](BENCHMARKS.md). CAD and graphics are tested separately.

## Curved-face groups, 26 October 2026

`curved_regions.py` processes multiple selected faces with nonplanar surfaces. Selected connected components are treated as separate group examples; each must contain 2–12 faces. Candidates are first filtered by surface type, area, perimeter, radius, and loops. The exact induced adjacency graph and one common rigid transformation/reflection of the entire group are checked. Examples from different bodies are not joined by invented topology.

Geometric evidence includes BRep vertices and triangulation of trimmed surfaces: nodes and triangle centers are checked in both directions against target triangles. Directed normals are also checked (dot product no less than 0.95 times the product of lengths), to avoid confusing opposite sides. Spatial tolerance is the maximum of linear tolerance and 1% of support-vertex diameter at default settings. An AABB index bounds spatial-query cost. This is a discrete shape check with tolerance, not proof of exact equality of arbitrary analytical surfaces.

A group remains atomic during ranking. For slots with a shared cylindrical axis and vertices at two end levels, the level plane is halfway between ends: same plane → parallel → others. This is slot depth position, not an arbitrary NURBS face normal. Undefined planes are separate and last. Exclude rejects the whole containing group. Without a verified additional analogue, the automatic level remains 0; approximate groups are available only through expansion.

Snapshot schema 5 stores immutable vertices, nodes, triangles, and normals; schemas 1–4 remain readable. Mesh is read only for potential roles of selected examples; adding Examples reads the required data. Limits: 160 new faces per read, 64 BRep vertices, 1,024 nodes and 2,048 triangles per face; 2 seconds for reading, 2 seconds/2 million states for search. Budget exhaustion or missing geometry produces an explicit refusal without a partial result. Individual curved faces still use scalar ranking.
