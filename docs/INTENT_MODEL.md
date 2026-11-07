# Selectra selection-prediction model

[Русская версия](INTENT_MODEL.ru.md)

Status: specification partially implemented on 25 October 2026. Planar polygon analogues, local wall pairs, shared geometry of repetitions, and native groups are implemented; validation scope and limits are in [EVALUATION.md](EVALUATION.md). Freeform surfaces, hole/shaft roles, and the complete matrix below remain unimplemented. The algorithm is in [RANKING.md](RANKING.md); terminology is in [GLOSSARY.md](../GLOSSARY.md).

## What is predicted

Scope clarification of 25 October 2026: Search Scope offers This Body / This Component / All Components, defaulting to This Component with nested instances of the selected component. References to the source body below describe the boundaries of graph/material relationships and This Body mode; shape matches can be sought across bodies in the selected scope. Canonical semantics are in [UX.md](UX.md).

The user selects elements as part of a task: work on identical edges, find paired sides of a wall, or select repeated holes. Selectra evaluates several possible grounds for that selection and constructs one understandable expansion order.

Required contract: source body only, same entity type, all explicit examples in the result, and all exclusions outside it. Neither inferred symmetry nor repetition expands scope to a neighboring body. Camera, visibility, and screen-distance features do not determine geometric similarity. The scope clarification above governs cross-body shape matching.

## Control scenario: thin wall

The example is an outer end face of a wall. Expected sequence:

1. The same outer face on the other side of the body: shape and size match despite changed position and orientation.
2. The inner face directly behind the example: shape differs slightly, planes are parallel, and a small material thickness lies between them.
3. The inner face at the found outer analogue: a more indirect relationship to the original example.
4. Remaining approximate analogues, in order of weakening geometric correspondence.

These numbers describe group order, not a promise of the same slider count for every part. Equivalent candidates are included together. In this example the user distinguishes the direct wall pair from the found analogue's pair; that distinction must not be erased by one sum of area and angle.

Overly simple rules fail: the nearest face can be a chamfer, the same perimeter can describe another shape, the same radius can describe a shaft instead of a hole, and a closer normal can indicate a distant transverse wall rather than a nearby parallel wall.

## Three sources of evidence

| Source | Considered evidence | Error prevented |
| --- | --- | --- |
| Intrinsic geometry | Surface/curve type, size, trimmed contour, loops, radii, boundary-segment sequence | Equal area and perimeter of different shapes |
| Relationship to examples | Parallelism, plane offset, projected overlap, reflection/rotation/translation, common axis | Missing a paired wall or symmetric analogue |
| Context | Neighboring surface types and angles, convexity, concavity, material thickness, structural repetition | Shaft instead of hole, random plane instead of chamfer |

Cheap features first select candidates; a more precise check confirms a particular relationship. A missing feature means unknown, not a match. Construction history can support a hypothesis, but imported STEP must remain a first-class case.

## Intent families

| Intent | Evidence | Insufficient features |
| --- | --- | --- |
| Same shape and size | Boundary correspondence in local coordinates under translation/rotation/reflection, loops and dimensions | Area, perimeter or edge count alone |
| Other side of a wall | Coincident normal axes, small normal offset, sufficient overlap, verified material between surfaces | Euclidean center proximity, one angle |
| Symmetric/repeated feature | Verified shape and a consistent transformation supported by several elements/context | Equal distance from bounding-box center |
| Same direction | Common edge or normal axis; directed normal is a separate explicit refinement | An arbitrary normal on a curved surface |
| Same size | Length, area or radius with suitable context | One shared scalar with an incompatible type |
| Same role in the part | Similar local context: hole, fillet, chamfer | Feature name or a single cylinder |

Edges use analogous relationships: same curve and length; corresponding edges of paired walls; same role between neighboring faces. Tangent chains and graph adjacency remain separate operations and do not replace similarity.

## Recognizing a wall pair

For planar faces, axis angle is `acos(abs(dot(n1, n2)))`. Reversing the outward normal by 180° alone does not reduce similarity. Directed normals are retained for material checks and explicit Orientation.

Then check:

1. Normal gap between planes, normalized to local size. No universal absolute thickness in millimeters is imposed on every part.
2. Projected overlap of trimmed regions. Expected changes from chamfers and fillets are allowed; a small incidental patch is not paired with a large wall.
3. Material between surfaces: several samples inside the overlap must confirm a local wall. A wall pair is not formed across an empty cavity. Boundary and uncertain samples do not count as confirmation.
4. Consistency with local context and other thickness estimates. Contradictions lower the hypothesis rather than being hidden by increasing tolerance.

Distance refines a suitable relationship class. A very close face of another shape does not outrank a verified shape analogue at the other end of the body. A centroid is not evidence of gap, overlap, or thickness.

## Choosing meaning without a criteria menu

At startup, several testable hypotheses from the table are formed. Each records its proposed relationship, examples explained, exclusions violated, supporting features, and missing checks.

Compare hypotheses in this order:

1. Compliance with scope, type, and explicit feedback.
2. Explanation of all examples without contradictions.
3. Strength of geometric evidence and separation of exclusions.
4. Specificity: prefer exact shape/role over a general “all planes.”
5. Minimal arbitrary assumptions; product priority for an exact shape analogue with one example.

A good average score cannot compensate for violating an exclusion. A shape cannot be called verified when only area and perimeter were checked. A normalized numeric score can be used within one evidence class; one global weighted average for all relationships is insufficient.

A second example is evidence about a relationship, not merely a reason to discard every differing feature. For example, outer and inner faces support “sides of one wall”; two parallel edges of different lengths support “direction.” Without a common explanation, retain examples and ask for refinement. Disconnected planar examples can define a union of families if each candidate is verified by one example's full contour. Losing size and shape and switching to all parallel walls is unacceptable.

## Producing one ranking of all elements

After interpreting feedback, each candidate receives its best verified explanation relative to **explicit examples**. Order is determined by relationship class, match quality, directness, and an appropriate local metric. Default product order:

1. Verified shape/size analogues, regardless of position.
2. Verified direct wall pairs of examples.
3. Verified related analogues, such as the inner side of an analogue in the first group.
4. Approximate analogues with weaker shape/size and contextual correspondence.
5. Other permitted elements with explicitly weak or unknown correspondence.

Groups 1–3 do not receive strong status without the corresponding checks. With missing data, a candidate remains approximate. For an explicit intent such as Direction, ranking follows it; the general shape ladder does not override the user's choice.

Every entity of the source type receives a place, including exclusions marked ineligible for inclusion. Indistinguishable evidence forms one level; tempId is not used to invent geometric order. PgUp/PgDown change only the boundary of an existing ranking. Ranking is rebuilt after an example, exclusion, or explicit criterion, not when the camera rotates.

Nesting is mandatory: expansion retains what is already included. Found elements do not become new examples; a direct relationship to an example and a relationship through a found analogue are explicitly distinguished. Transitive chains do not cause uncontrolled propagation. Maximum range includes all non-excluded elements of the type; a message explains the meaning of a broad range.

## Feedback and explanation

The primary interface remains Examples, Exclude, range, and OK. A short status describes the current basis: “Same shape,” “Added the inner wall side,” or “Shared dimensions; shape not verified.” Do not show raw weights and confidence percentages.

Adding an example supports hypotheses that explain it together with the others. An exclusion prohibits the element and weakens hypotheses that would include it on the same basis. A geometrically indistinguishable example and exclusion produce an honest limitation message.

If two hypotheses produce the same result, users should not have to choose between their names. If results diverge and evidence is weak, show a small justified set and use one additional example or exclusion for refinement. No mandatory questionnaire is required.

PgDown means “this range is too broad”; it does not turn every removed face into a negative example. PgUp likewise does not endorse each added element as an example. OK confirms the set for this command and does not by itself train global user habits.

## Implementation architecture

Four independent layers: geometry snapshot → relationship checks → intent-hypothesis evaluation → stable selection levels. Native UI receives only levels, explanation, and ambiguity state.

Each relationship requires type, source examples, target, evidence quality, measured errors, and reason for rejection/uncertainty. Explanations are stored structurally and cannot be reconstructed afterward from one number.

Time/check-count limits do not permit calling unchecked candidates exact. A cheap stage yields a fast preliminary set; the exact stage completes atomically and does not move the range under the user. On budget exhaustion, report incomplete analysis explicitly and block applying unchecked results. Geometry and timeline do not change.

## Corpus and quality criteria

| Scenario | Required order/refusal |
| --- | --- |
| User's thin wall | Outer-face analogue → example's inner pair → analogue's inner pair |
| Distant exact analogue and nearby chamfer | Analogue before chamfer |
| Equal perimeter, different shape | Do not call it an exact analogue |
| Two parallel walls across a cavity | Do not call them a material pair |
| Narrow chamfer next to example | Proximity does not prove a wall pair |
| Hole and shaft with equal radii | Separate by verified role or report insufficient data |
| Rotated/mirrored repetition | Retain shape analogue when normals change |
| Two dimensional families | Do not expand to all entities after losing shared features |
| Fully equivalent elements | One level; tempId order has no effect |
| Rotated/translated model, different camera | Preserve semantic ranking |
| Identical neighboring body | Include none of its elements |

On a labeled corpus, measure first-group correctness; PgUp/refinement count to reach the target set; extra/missed elements; wall-pair correctness; ranking stability after insignificant changes; and p50/p95 read, analysis, and highlighting times separately. Variants of one part must not appear in both training and control groups. Do not claim accuracy percentages or intent probabilities before such measurement.

## Implementation order

1. Preserve regression coverage for the current normal error. Already done: Automatic compares the normal axis with lower weight; explicit Orientation remains directed. This is a local fix, not a complete wall recognizer.
2. Add a testable trimmed-boundary signature and shape correspondence under translation/rotation/reflection. Do not rely only on scalars.
3. Extract plane positions and local geometry; implement overlap, gap, and material checks for a wall pair.
4. Introduce relationships/hypotheses/explanations and replace global feature mixing with comparison of evidence classes.
5. Add symmetry and repetition, then hole/fillet/chamfer roles with their own negative examples.
6. Complete the labeled corpus and native CAD acceptance before claiming automatic intent understanding.

## Plane ordering clarification, 25 October 2026

Within each shape/size family, Automatic separates matching, parallel, and other planes into sequential levels. This applies to circles/arcs as well: equal hole radius does not immediately group its outer and inner edges. The world support plane is checked, not screen depth. Unknown planes come last within the family. Additional explicit examples expand the set of support planes.

## Curved slot sides, 26 October 2026

Several selected inner slot faces can form several connected parts on different bodies. Each connected example is sought as a complete group with geometry and adjacency preserved. Cylindrical/NURBS support uses a discrete check of the trimmed surface, common transformation, and normals. This is separate shape evidence, not an inference from area. Plane order applies to the whole group by extrusion level so parts of one slot are not split across steps.
