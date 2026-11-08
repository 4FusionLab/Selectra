# Selectra: product workflow

[Русская версия](UX.ru.md)

## Promise

Show an example and obtain similar elements in the selected scope. By default, this is the example's component and nested hierarchy. The tool starts with a reasonable proposal and lets the user refine the result without first choosing a technical criterion.

The speed of Blender selection is a reference point. Selectra's distinguishing features are analytical CAD geometry, automatic selection of shared features, learning from additional examples and exclusions, and a ranked range. The target model of geometric relationships and intent is in [INTENT_MODEL.md](INTENT_MODEL.md); this document describes the interface and current behavior.

## Main path

1. The user selects an edge or face and chooses **right-click → Select Similar**. Already selected elements become examples. Entity type is fixed; the default scope is **This Component**.
2. The proposed set immediately receives **Magenta highlighting**: examples and the first nonempty group of matches. Fill opacity is 35% to reveal overlapping planes. This is temporary; the actual result selection has not yet been applied. There is no Preview field or Wheel toggle.
3. Usually **OK** is sufficient. The user receives an ordinary Fusion selection and starts the desired native operation.
4. If the set is too narrow or broad, **PgUp / =** adds the next similarity level and **PgDown / -** removes the weakest included level. The Similarity slider does the same. The mouse wheel retains normal Fusion navigation.
5. If the tool chose the wrong meaning of similarity, the user adds a second example in **Examples**. To identify an unwanted element, use adjacent **Exclude**. This recalculates the ranking and restores the automatic range.
6. **Cancel / Esc** removes temporary highlighting and restores the original selection. Starting another command is not treated as pressing OK.

## Compact native dialog

The main area shows result count and scope, **Search Scope**, Examples and Exclude, the **Similarity** slider labeled **Closest / Broader**, the hint **PgUp / =: more | PgDown / -: fewer**, OK, and Cancel.

**This Body** is limited to the example's body in its particular instance. **This Component** includes bodies in the selected component and all nested components of that instance. Neighboring instances of the same definition are excluded. For a root-component body, its hierarchy is the entire assembly. **All Components** covers visible accessible BRep bodies throughout the assembly, including nested instances.

Changing scope rebuilds the snapshot and restores the automatic range. Examples can be added from any body in the selected scope. If narrowing would leave explicit examples outside it, the user removes them first; scope does not change silently. Exclusions outside the narrowed scope are removed from Exclude. Current scope is always shown in status. If expansion fails, the previous scope remains with a message; a partial set from the new scope is not applied.

**Refine** is collapsed. It contains optional **Match** (Automatic or a specific feature) and **Reset Range**. Technical features remain available for reproducibility, but automatic mode is the default. A large settings palette, confidence percentages, and mandatory criterion selection are unnecessary.

The user sees the result on the model, not a list of tempIds. The included-element count updates with highlighting. Changing examples does not create geometry or modify the timeline.

## Ranking and range control

All entities of the selected type in the current scope receive a similarity distance. Adjacency and material relationships are checked within each body; shape matches may cross bodies. This is a geometric order, not an intent probability.

Automatic mode uses available features: geometry type, length/area, radius, direction/normal axis, perimeter, and a simple boundary signature. The inner side of a thin wall is not considered less similar solely because its normal is reversed by 180°. Orientation is weaker than size and shape; exact direction is available through Match → Orientation. If two examples differ on a feature beyond tolerance, it ceases to be a mandatory shared property. Exclusions strengthen features that distinguish them from examples.

Original examples remain at every range; exclusions are not included even at maximum expansion. Equally similar elements are added and removed together: identifier order must not arbitrarily split the group. One PgUp step can therefore add several elements.

Ranges are nested: expanding keeps included elements; narrowing removes the least similar. At maximum, all permitted elements of that type in the body can be reached. This is not a neighbor search or geometry modification. Graph More/Less, Linked, and path search are separate operations; PgUp/PgDown are not bound to them.

The initial automatic range immediately includes the first available group of similar elements beyond the examples; Reset Range restores it. If no candidates exist or shared features are insufficient, the tool retains examples and asks for refinement. If an exclusion is geometrically indistinguishable from an example, this is reported; an arbitrary distinction is not presented as recognized intent.

## Highlighting behavior

The last included level receives an additional 3 px outline. When expanding, the emphasis moves to the added group; when narrowing, it moves to the outermost remaining level. The outline does not blink; earlier faces retain a 35% fill and edges a 1.5 px Magenta outline. Short status text distinguishes a verified shape, wall side, repeated group, and approximate similarity. The maximum is explicitly labeled as all permitted elements of the body's original type.

Magenta highlighting must remain in place when input stops, the cursor moves, parameters change, and the view rotates. Temporary objects do not intercept mouse selection.

Overlapping surfaces use an overlay effect and depth priority. Real face coordinates are not displaced. Graphics are created in the command's native preview event; a valid group is reused, and elements are hidden/shown without clearing the entire frame. OK/Cancel/Stop removes the complete group.

Disappearance caused by the preview lifecycle and depth conflicts on overlapping surfaces are checked separately. Stability is not established merely by created CustomGraphics objects: visual validation in Fusion is required.

## Experience acceptance criteria

- One example can produce a proposal and be confirmed without visiting Refine.
- PgUp/PgDown and the slider control one ranking; adjacency does not determine similarity order.
- Highlighting is continuous and Magenta, matches the set after OK, and does not become actual selection before confirmation.
- An additional example and exclusion change search meaning predictably; Reset Range restores the automatic range.
- Cancel and interruption preserve the model and leave no temporary graphics.
- Unknown features, display-budget exhaustion, or a changed body produce a clear message without partial application.

This document records target behavior and the kernel contract. Actual CAD acceptance is recorded separately in [VALIDATION.md](VALIDATION.md).

For the same geometric group, Automatic first proposes elements in the example plane, then in a separate step those in parallel planes, then others. For example, hole edges on a plate's outer side precede inner edges on the reverse side. Status shows In the example plane / In parallel planes / In other planes; an absent support plane is labeled Support plane unavailable.

Several disconnected planar Examples can define different size families. Automatic first shows verified analogues of each example with the explanation Matching shapes and sizes of the examples. Connected examples can define a repetition of the complete group; a shared plane alone does not replace shape checking.

Selected inner sides of a slot may include cylindrical and NURBS faces. Connected parts are searched as complete groups: one arbitrary similarly sized face cannot be included alone. For an extruded slot, level order follows its end plane: same → parallel → others. Matching curved-face groups (sampled geometry) indicates a discrete shape check.

## Select Chain

A separate context-menu command for one or more selected BRep edges or wall faces. Every proposed contour at every level must pass through all examples. An edge defines the nearest closed edge loop; a face defines a closed traversal of adjacent walls around a neighboring face loop. Closure comes from BRep topology, not visual resemblance. For walls, continuity of neighboring traversal members is checked. Seams that traverse one edge repeatedly are not simple edge loops.

**Chain across contact** is enabled by default: a chain can cross completely coincident shared faces of visible bodies, as after Split Body. Point/edge coincidence, partial contact, a gap, and volume overlap do not count as such a junction. With the checkbox off, bodies remain separate. Every contour must pass through all examples. Among those, contours in the examples' plane rank first, then parallel, other, and undefined-plane contours. Within that order, inner loops and perimeter are considered. Switching selects only alternative closed traversals through the same examples. Neighboring holes and contours without the chosen element are excluded even at maximum. Different equally ranked contours remain separate options. This is a nearest-contour heuristic, not the only mathematically possible interpretation of a wall.

Contour, PgUp, and = choose the next complete contour instead of the previous one; PgDown and - return to the previous option. Exactly one contour is displayed at a time, without accumulation. The example is retained. Highlighting is Magenta; selection transfers only on OK; Cancel restores the original example. If no closed chain exists, a clear message is shown and OK is disabled. Examples allows adding and removing examples; Search Scope, Match, and Exclude are not shown here.

Cross-contact transitions are checked on temporary BRep copies; no real Combine, Stitch, or timeline modification occurs. A closed contour is constructed after virtual removal of internal seams and mapped completely back to original edges/faces. If examples on separate bodies do not belong to one contour with the checkbox off, they remain selected, No closed contour passes through all examples is displayed, and OK is disabled. The slider, PgUp/PgDown, and =/- continue adding whole contours.

For an edge, plane is determined from its known support planes; for multiple examples, common planes are used. A straight edge can have several. If the example plane is undefined (for example, for a wall), the plane of the nearest suitable closed contour is used. Every step adds a whole loop through all examples. Plane coincidence and geometric adjacency do not replace this mandatory condition. Status shows In the example plane / In parallel planes / In other planes / Contour plane unavailable.

Chain across contact adds cross-body options to the source bodies' contours. It does not replace the source-body catalog with temporarily united geometry: contours along the Split Body boundary remain available even if virtual union removes that seam. Every option still passes through all examples.

For edges, shared boundaries of smoothly connected face groups are also available: for example, the complete outline of three inner walls of half a slot. Internal junctions of those walls are not part of the contour. If a group has several separate closed boundaries, each remains an independent option; only those through all examples enter the search. Simple adjacency or coincident endpoint coordinates do not prove closure.

For faces, the search also recognizes a closed strip of several adjacent faces of one body when it has two complete simple boundaries and a simple cycle of cross junctions. Narrow strips rank before traversals of neighboring faces; their order depends on the ratio of mean junction length to the smaller boundary length. This is a heuristic: for a wide or complex strip the order can differ from expectations. Search is budget-limited and does not return a partial result when exceeded. This additional check does not yet recognize cross-body strips.
