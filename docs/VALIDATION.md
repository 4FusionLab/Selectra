# Selectra validation in Fusion

English | [Русский](VALIDATION.ru.md)

Status 10.25.2026: **partial native acceptance completed** in Autodesk Fusion 2706.1.14 on macOS. At first, development was completely offline; After the user's permission, tests were performed on his open model. The complete matrix below remains the protocol for the following checks.

Locally after geometric iteration: 134 Python tests - OK; compileall, metadata/SPDX/links and ZIP/SHA-256 - OK. These checks do not replace CAD acceptance. The historical baseline acceptance below was performed with 64 tests.

## Geometric iteration 10/25/2026

### Correcting internal face reading

After the user message, the defect on the selected internal face of the current body was reproduced: instead of its opposite internal analogue, the outer side of the original wall came first. The area and perimeter of the internal analogue were the same, but the contour was read incorrectly. For some BRep edges, the direction of the evaluator parameterization is opposite to the direction of the edge itself; Only coedge.isOpposedToEdge was taken into account, without edge.isParamReversed. Large jumps appeared between successive sections of the erroneous boundary.

Both orientations are now XORed, continuity and closure are checked before the outline is passed to the kernel. The `tests/test_fusion_contours.py` protocol test reproduced the failure on a synthetic circuit with mixed parameterization and passed after correction. On the original selected face, after correction, the first level again contains only the opposite internal analog with the shape explanation; the outer pair has moved to the next level. User geometry is not included in the regression corpus.

### Basic iteration acceptance

To correct the orientation, it is the registered reloaded add-in in the open user document that is re-checked: the initial set is the original internal face and its opposite internal analogue. The temporary graphics coincided with the set; the next levels are the direct outer pair and the analogue pair. Geometry, revision, area, volume and number of faces/edges remain the same. After the fix, 135 Python tests are passed; the synthetic corpus maintains results of 11/11 and 5/6. The corrected preview is left open to the user.

Fusion 2706.1.14, macOS, registered add-in of the current working branch. The main coordinator worked consistently; subagents performed only offline tasks.

In a separate unsaved document, a closed thin-walled body was created: 12 faces, 24 edges, external size 10 × 6 × 2 cm and internal cavity 9.6 × 5.6 × 1.6 cm. The second identical body is excluded from the search area. Reproducible fixture - `tests/fusion_geometric_acceptance.py`; it uses the calculated BaseFeature bodies after finishEdit, rather than references to edit bodies.

- The full snapshot contains 12 faces and 6 local pairs of walls. The first three groups: external analogue → internal side of the example wall → internal side of the analogue. The exact entities and their parent body are verified.
- PgUp: 2→3 faces, PgDown: 3→2. The last level has a separate circuit; Visibility and reuse of graphics are checked by readback, fill and outline are checked in the UI. Opacity of both faces: API `(True, 0.349999994, True)`.
- Two preselected examples of opposite sides set wall_sides: exactly 4 faces of the two corresponding walls are selected. After this OK activeSelections exactly matched the preview; graphics groups = 0.
- Two related examples of different sizes define repeated_region. Exactly 4 external faces of the corresponding nodes are found; initial analysis about 1.4 ms, highlighting about 92 ms.
- This Cancel restored the original example; graphics groups = 0. After all the checks, the fingerprint of the geometry/timeline of the test and source documents matched. The created document is closed without saving, the original one is activated; User documents were not saved or closed.
- A separate body 4×4×0.2 cm with a narrow closed cavity between the sample depths showed the falsehood of only five point samples. An intersection check of the entire route rejected this pair; There is no false connection in the picture.
- On the tested core, ray proximityTolerance 1e-7 cm returned empty collections; 1e-6 cm gave consistent hitPoints and entities. 1e-6 cm is used with mandatory confirmation of reaching the opposite face. A blank/inconsistent result is not considered evidence of material.

First normal fixture run: BRep 2.37 ms, topology 0.58 ms, relations 1.77 ms; total reading 4.86 ms, analysis 0.48 ms, graphics 70.16 ms. This is a small synthetic part; scalability does not follow from here.

After the final add-in reload, an additional read-only smoke of the current source was performed on the open user model: 39 faces, full scope, 11 connections with local material evidence, 6 ranges for the selected flat face. BRep 17.73 ms, topology 4.54 ms, relations 127.00 ms, total read 149.67 ms, analysis 9.22 ms. Geometry, revision, visibility and timeline before/after matched. The correctness of each of the 11 relationships in this smoke was not manually assessed; The new UI preview on the user part was not launched.

Exclude in the live dialog was not accepted in this iteration: the attempt by the external test handler did not add an element to the CommandInput, so it is not counted as a check. The pure core and exception restrictions are covered by tests. Camera rotation, a full interrupt matrix, real STEP and Windows are still required for the new implementation.

## Completed in Fusion

- The add-in from the current checkout is normally connected, Run on Startup is disabled. Temporary MCP imports are not used as proof of UI.
- Adding Select Similar has been confirmed in the current RMB menu event.
- One root body: 97 edges, 39 faces. The Read-only contract checked 8 examples of each type: the ranking is complete, the ranges are nested, the maximum covers all valid entities of this body.
- Edges: initial ranked set 4; PgUp gave 8; PgDown returned 4. In reality, OK activeSelections exactly matched the fixed keys of these 4 edges.
- Edges: initial set 2; PgUp gave 3; PgDown returned 2. Magenta overlay is visible on real surfaces, including through overlapping geometry.
- After a pause, the graphics remained visible without a new frame. After eliminating the double doExecutePreview, there is one updated frame per range change.
- On a user example of a thin wall, an erroneous order was reproduced: the transverse internal face came before the parallel one due to the directed normal. The corrected Automatic is tested on a full unaltered body shot: external similar → parallel internal → transverse internal. A separate regression test preserves this order, and an explicit Orientation preserves directional semantics.
- After reloading the current add-in using the same example, the starting level 1 with two faces and the order of the following groups were confirmed. Native getOpacity returned 0.35 with override for both graphic faces; the fill became visually translucent. The value is stored by the API with float precision.
- Cancel returned the original face. After OK and Cancel customGraphicsGroups = 0.
- In the control session, volume, area, number of faces/edges, visibility, body revisions and timeline were compared: there were no changes. The document was not saved.

The offline kernel additionally checks for exceptions, feedback conflict, history, equal scores, explicit criteria, scope/revision, and limited similar region searches. The presence of these tests does not mean that all relevant UI scenarios have already been passed.

## Acceptance of assembly areas and keys =/- - 10.25.2026

Implemented This Body / This Component / All Components; the initial mode is This Component. It includes the bodies of the selected instance and its child hierarchy. For the root component, this is the entire assembly. Visibility and selectability are taken into account when reading.

The bodies of the root component, two instances of one definition and another nested instance are built on a separate unsaved document `tests/fusion_scope_acceptance.py`; then the child component of the selected definition is added. Rotations around different axes and translations were tested.

| Mode | Region bodies/faces | First set |
| --- | --- | --- |
| This Body | 1 / 6 | 2 |
| This Component with child component | 3 / 18 | 6 |
| All Components | 10 / 60 | 20 |

Modes were switched with a real native list. All keys are unique, the temporary BRep fill coincided with the world boundingBox faces with an error of less than 1e-6 cm; contours - less than 1e-5 cm (graphic coordinates float32). After OK, activeSelections contained exactly the expected 20 original proxy faces; graphics groups = 0. Cancel also cleared the graphics and restored the original selection.

The keys =, -, PgUp, PgDown on the same range gave respectively 18, 6, 18, 6 faces, levels 2, 1, 2, 1. Shift is taken into account, which the current layout transmitted along with =; Ctrl/Alt/Meta does not intercept these aliases.

Separately checked: the hidden instance with a child component was not included in All Components; the change to transform2 made the previous scope guard invalid; This Component for the root body covered the entire assembly. On the thin body inside the rotated specimen, native material testing confirmed a pair of walls. Two initial examples from different bodies of the same component correctly obtained different key spaces and the overall result.

A user design previously rejected due to assemblyContext was read without changing the geometry. In the last visibility snapshot: This Body - 57 faces; This Component - 2 bodies / 114 faces; All Components - 5 visible bodies / 338 faces. Total reading: 0.430 / 0.432 / 0.504 s, pure analysis: 0.028 / 0.071 / 0.074 s. In an earlier visibility snapshot, All Components included 14 bodies/428 faces; changing user visibility is not considered a regression. Failure of the optional wall stage communicates the constraint and resets its pairs entirely; full entity readings and available form proofs are preserved.

This iteration runs 140 Python tests; real Windows CAD and the entire release matrix remain open. User documents were not saved or closed, test documents were closed without saving.

## Still required

Full manual check of Examples/Exclude and all Match modes, various user parts and STEP, large highlighting budgets, interruption by another command/change of document in all phases, application of the resulting set in standard operation and Windows Fusion. Some Native topology/Face Regions UI commands are not yet enabled; automatic repetition on related examples is checked above.

Use a separate unsaved document. One CAD session; do not close or change user documents. Record the original active document, OS, Fusion version, path of the loaded add-in and the number of bodies/faces/edges.

## Corpus

Create a root body with edges of the same length in different directions, parallel edges of different lengths, circular edges and cylinders of several radii. Add a second body with identical features as a negative example of an area. Separately - STEP with similar geometry, flat faces of equal area with different perimeter, oppositely directed planes, inner and outer cylinders of the same radius.

## Matrix

| Check | Criterion |
| --- | --- |
| RMB with selected edge/face | Exactly one Select Similar, standard items saved |
| RMB without choice / mesh / mixed types | Command not offered |
| Two examples of one body | The kernel uses both, the order does not affect |
| Examples of different bodies | Explicit failure without scope expansion |
| Search with the same second body | Zero results from the second body |
| Component occurrence | There is a clear failure in spike; after step 4 - only the selected body of the selected instance |
| Preview | Magenta is constant, the number corresponds to the ranked range, there is no Preview field |
| Refine | Changing examples/exceptions and criteria does not re-read the entire BRep; no recursion |
| No matches | Examples are saved, the range can be expanded, Cancel works |
| OK | After closing, the selection matches the Magenta highlight, ready for normal operation |
| Cancel/Esc | With the same document and default Select, the original examples are restored |
| Abort by another command | Selectra is not executed implicitly and does not overwrite the selection of the new command |
| Change document to idle | Deferred migration does not change the new document |
| Invalid entity | Controlled failure, no partially applied set |
| Stop/Run | Handlers and commands are not duplicated; deferred callback after Stop does not change the choice |
| Model before/after | Bodies, geometry, timeline and modified state are not changed Selectra |
| Dense perforation | Reading, ranking and mass illumination were measured separately; refusal according to the limit is not given as a full result |

Check the geometric consistency of each result, not just the number of elements. On two externally identical bodies, it is not enough to check the quantity: check the parent body of all selected objects.

## What to save in the report

For the scenario: model parameters, initial tempId within the unchanged body, selected hypothesis, expected/actual set, durations and a screenshot where a visual result is needed. Comparing entityTokens as strings is not allowed; Resolve long-term identity via API.

Local tests test hypotheses and numerical tolerances. Static API definitions validate the existence of methods, but not the order of events, drawing, or saving selections. Only this matrix on a real Fusion closes technical acceptance.

## Plane order - native check 10/25/2026

On macOS, in a separate unsaved DirectDesign, the `tests/fusion_plane_acceptance.py` scenario was executed: a plate with four through holes of radius 0.2 cm and a separate perpendicular cylinder. The original instance is rotated 0.35 rad around Y; the second instance of the definition is rotated around X and moved. The user document has not been edited.

In This Component real = and PgUp gave 4 → 8 → 10 circular edges: selected hole entry plane → parallel back → perpendicular cylinder. In All Components we got 4 → 8 → 20: the edges of the other rotated instance were added only in the third step. The radius of each entity, plane classes and the correspondence of the renderer keys to the result were checked. After updating the graphics, all included edges had a visible outline; the first level retained a weight of 1.5 px, the new one - 3 px. The screenshot confirmed that Magenta remained on the holes when adding a second level.

OK in All Components transferred exactly 20 expected proxy entities to activeSelections. There are no residual CustomGraphicsGroups. The test document is closed without saving, and the original user document and its selection are restored. This is a test of reproducible hole geometry, not an exact reproduction of a changing user part selection, and not a Windows CAD acceptance test.

## Multiple shaped regions - check 10/25/2026

The current user selection of two unrelated planar faces of different bodies of the same component reproduced the defect: the first set of 26 faces contained large walls, the hypothesis is parallel_planes. The areas of the examples are about 1.08035 and 1.11800 cm². Separately, the search also lost analogues due to different numbers of sampling points for identical curves.

After correction on the same unchanged choice, the live preview gave 6 shaped faces (three from each family), hypothesis shape_families. Real key = added 6 more analogues in other planes; - returned the first set of 6. Specific session-local keys, renderer.keys, absence of preview_error and visual Magenta highlighting were verified. Pure analysis of a local numerical image took about 0.37 s, construction of native graphics - 0.098 s. Rearranging the two examples preserved the entire ranking. Preview is left to the user at the first level; OK was not pressed, the geometry and timeline did not change. User geometry is not included in the public corpus.

Regressions in the core: unconnected families instead of all parallel walls; the same curvilinear border with different numbers of points, rotation and reflection; general transform of the outer boundary and holes at different sampling rates. Linked repeat node and wall pairs preserve existing tests.

## Inner sides of grooves - 10/26/2026

Using the current selection of six internal faces of a user part, the seed-only result is reproduced: two unrelated samples of three faces each (a cylinder and two NURBS). After finalization, the live preview showed 12 corresponding faces in the original plane; = added 6 more in other planes. This snapshot does not have an intermediate parallel group. The exact result keys, renderer.keys, absence of preview_error and visual Magenta highlighting were checked. Pure analysis - about 0.19 s. The user geometry did not change.

Full native acceptance was performed in the same CAD session on a separate unsaved copy of the two bodies created by `tests/fusion_curved_acceptance.py`. The six original faces are compared with copies by type, area, and world BRep vertices. The resulting sequence is 12 → 18 → 12 by real =/-. OK moved exactly 12 expected entity references, CustomGraphicsGroups cleared. The original body_stamp and isModified remain the same. The copy was closed without saving, the original six examples were restored. In the user document, the first-level preview is reopened without OK. The model geometry is not included in the public corpus.

Seven new Python regressions test whole group, individual levels same/parallel/different plane, example order invariance, whole group exclusion, misalignment rejection, surface overhang when vertices coincide, normal misdirection, rotation/reflection, missing mesh data, budget, and serialization. This is discrete evidence of a surface, not an analytical proof that arbitrary NURBS surfaces are equal. Windows CAD is not verified.

## Select Chain — 26.10.2026

In one native macOS CAD session, `tests/fusion_chain_acceptance.py` was executed: a separate unsaved pocket (outer parallelepiped 6x5x3 cm, cutout 4x3 cm, four inner walls) and a second identical body nearby. From one inner wall, Select Chain produced exactly four expected walls, without the bottom, rim or outer edges. = expanded the set to six faces; - returned four. Screenshot confirmed the stable Magenta highlighting of the walls. OK transferred exactly four expected BRepFaces, graphics cleaned up.

Exactly four edges of the original loop are obtained from one edge of the inner rim. Real PgUp/PgDown gave 4→7→4 edges. Cancel restored the single original edge; restart and OK retained exactly the expected four BRepEdge. At all steps, the parent body of each result was checked: nothing was selected in the neighboring body.

The native context menu event with one edge selected added both commands without errors; Select Chain registration and execution verified. The popup menu was not available in the screenshot of the selected window, so the visual position of the item was not confirmed by this run. The test document is closed without saving, the original document and selection are restored. Python tests cover whole levels, internal priority, duplicates, equal proofs, unchaining, and unreachable loops. Windows CAD and arbitrary complex walls require a separate test corpus.

## Select Chain via precise contact - 10/26/2026

The actual user selection of two NURBS edges of different body halves (Body1/Body2 of one instance) reproduced the failure of the old single-example/single-body mode. The complete coincidence of common faces is confirmed by the two-sided empty difference of BRep surfaces; solid intersection is empty. After a temporary union and reverse mapping, the closest contour contains the six original edges, including both examples. The analysis took about 0.9 s. Along one internal NURBS face of the same groove, six original walls in a circle were found (about 1.1 s). The geometry of the user part is not saved to the public body.

Separate unsaved CAD fixture `tests/fusion_contact_chain_acceptance.py`: two halves of a plate with a through hole in a rotated and transferred occurrence. Full contact accepted; gaps 1e-5, 1e-7 and 1e-8 cm, partial contact, edge contact only and overlap rejected. From two initial arcs, with Chain across contact enabled, a closed circle is constructed, the result was reduced back to exactly two original arcs. Unchecking the checkbox saved the examples and disabled OK with an explicit message about the lack of a common outline; turning it on again brought it back.

For one cylindrical wall, the enabled checkbox gave two halves of the inner wall on two bodies; turned off limited the result to the original body. When you turned it on again and OK, exactly two expected original faces were selected. Both options are OK, checked for links and absence of residual CustomGraphics. The test document is closed without saving, the original selection is restored. In the user document, a preview of six edges through the original two examples is open, OK is not pressed. The slider and keys use the same general lifecycle; Windows native scan was not performed.

A separate negative check found that the ASM initially accepted a partial joint with an in-plane offset of 1e-8 cm. The reproducible assert initially failed. After adding strict two-way edge matching, this shift is rejected, the true zero-gap contact is accepted, and the original user halves are still joined in about 0.9 s. Checking for normal clearance alone would not be sufficient.

## Contour plane and launch along one edge - 10.26.2026

The user specified the expected flat loop of six groove edges of two touching bodies. When running along one edge, the old mode chose another, spatial traversal of six edges. Diagnostics showed two reasons: the priority of the perimeter/neighborhood over the plane and the absence of the required loop among the candidates. One arc was mistakenly excluded from the reverse matching: its BRep vertex lies slightly outside its own analytical circle within the ASM tolerance. The curve completely coincides with the original one, which is confirmed by the two-sided empty difference of the wires. The curve's own points are now used for matching; strict check of contact of bodies, including BRep-vertices of the boundary, is preserved.

On the same user document, running one edge at a time gave exactly the expected six BRepEdge entities at the first level, including the previously lost arc; status In the example plane. Real =/- gave 6→12→6 edges, both first contours are in the original plane. Screenshot confirmed the entire Magenta loop of the required groove.

On a separate unsaved rotated Split fixture `tests/fusion_contact_chain_acceptance.py`, launching along one arc gave a complete contour of two initial arcs of two bodies. = and PgUp gave 2→8→10 edges: the first and second groups are coplanar, the third is parallel. PgDown/- returned the first set; OK saved exactly two expected entity references, no residual graphics. Gaps, partial contact, small tangential shear and overlap are still rejected. The test document is closed without saving. The user document has been restored; preview is left on the first contour along one edge without OK.

Python regressions check the priority of a large coplanar loop over a short spatial one, integer levels of the same/parallel/remaining/unknown plane, candidate order, rotation/reflection/translation, and preserving the condition of passing the first loop through the example.

## Select Chain: mandatory passage through selection at every step - 10/26/2026

The user clarified the meaning of the operation: only contours passing through the selected edge/face are needed, and not neighboring loops in the same plane. The previous selection limited only the first step to this condition, and ranked the rest by graph proximity; this was a specification error. The graph extension has been removed from ChainSelection. Now each candidate contains all examples before ranking; plane, inner loop, and perimeter are the only candidates that order.

Three fixed/new Python checks initially failed: an adjacent coplanar loop would fall into the expansion, contours would appear at maximum without one of the two examples, and the pass check would be limited to the first level. After correction, all ranges exclude these candidates.

On the current user edge, exactly two valid contours are obtained, each containing the original edge. The first gives the desired flat loop of 6 edges. = adds an alternative spatial traversal through the same edge (10 edges in total), repeated = at maximum adds nothing. - returns 6. The complete set of all included edges is verified with the union of only contours through the original example; adjacent holes are not included at any level.

In a separate unsaved rotated Split example, a single arc run has only one valid closed loop: the two original arcs of the two bodies. Real PgUp/= do not extend it with extraneous loops. For one wall, only the corresponding closed chain of walls remains. Both OKs give exactly the expected source links; graphics have been cleaned up. The test document is closed without saving; the user selection is restored and preview is left on the first circuit. This replaces the erroneous expectation of extension 2→8→10 from the previous protocol.

## Select Chain: individual options and contour of the original body - 10.26.2026

The user showed a missing closed loop of 8 edges in its entirety on Body2, including two edges along the cut boundary. The reproducible check initially failed: with Chain across contact, the contour was not in the catalog; when the contact was turned off, it was present. The reason is that the temporary union removed the seam, and the catalog was built only on the virtual body. The fix preserves the original loops of each body and adds end-to-end loops. For one edge of a user part, four separate options are obtained: 6, 8, 4 and 6 edges; the first two are coplanar. The second option exactly matched all eight entity references selected by the user.

According to the refined semantics, PgUp/= selects the next full contour instead of the previous one, PgDown/- returns the previous one. There is no accumulation and merging of different equal options. The full contour does not disappear from the list, even if all its edges were found in other options. Each option goes through all the examples at each step. For Select Similar, the cumulative range is preserved. This replaces the previously erroneous behavior of the Select Chain extension.

In the user document, real = switched 6→8 edges. The exact match of the second option with the shown outline was checked and the graphics of the first option that were not included in the second were hidden; the geometry did not change.

In one separate unsaved CAD session, a `fusion_contact_chain_acceptance.py` fixture was made on the rotated halves of a plate with a hole. Full joint accepted, gaps, small tangential shift, partial contact and overlap rejected. There are three options for one arc: a through circle of 2 original arcs, the native contour of half the body of 6 edges, and the border of half a wall of 4 edges. Real =/- gave 2→6→4→6 with replacement of the highlighting. In the second option, all edges belong only to the first body; the graphics of the previous through loop are hidden. OK allocated exactly 6 expected source edges, CustomGraphics cleared. The test document was closed without saving, the user document was restored.

Python regressions check that all variants are strictly related to the original examples, the absence of accumulation, the separate search of equal variants, the preservation of contours from previously used edges, and the availability of the original cut line along with the end-to-end contour.

## Common boundary of three smooth walls - 10.26.2026

The user showed another missing 8-edge contour on Body2: the front and back profile of the groove half, connected by two depth edges at the cut. The user confirmed the previously found four options and their order. Checking tangentiallyConnectedFaces revealed a group of cylindrical and two NURBS walls; its general boundary coincided exactly with the highlighted eight links. The old catalog contained the boundaries of individual faces, but not the overall boundary of that group; the absence check was reproduced before correction.

After adding the boundaries of smooth groups, 6 options were obtained; the previous four remained first in the same order. The new contour shown is the fifth one, closed and non-planar. Full match with user selection was checked using the links. Enumeration remains the replacement of one option with another, each passing through the original edge. Reading/searching in the current example took about 1.3 s. The geometry of the user project was not saved to the public corpus.

Native acceptance of `tests/fusion_patch_chain_acceptance.py` was carried out in a separate unsaved document: the plate with the capsular groove is divided in half, both halves are placed in a rotated occurrence. The required contour was specified independently according to the geometry of the model: three front, three rear edges and two end ones, 8 in total. Based on one edge, the fourth option was found - the exact common boundary of the three tangent walls. Checked the original entity references, no accumulation and hiding of graphics of other options. OK transferred exactly these 8 edges, there are no residual graphics. The test document is closed without saving, the user document and selection are restored.

Five new Python regressions test for internal edge elimination, common three-wall traversal, split front/back rings, periodic seam, circular loop, open/branched border failure, incomplete data, and over budget.

## Intermediate parts of the smooth section - 10.26.2026

Two user examples, edges 1470 and 1690 Body2, reproducibly produced zero variations. The common boundary of two adjacent faces 1695 and 1689 contains both examples and 10 edges. In a full smooth section of nine faces, edge 1690 becomes internal and is eliminated; the catalog of individual faces and the complete section therefore skipped this walkthrough.

Added enumeration of connected intermediate parts of smooth sections with proof of closure based on the exact vertex topology. Duplicate boundaries are excluded before planes and lengths are read, and edge information is cached per section. After correction on the current project, 42 different contours are found through both examples, the expected 10 edges come first; reading took about 2.4 s. The previous four options for one edge remained first in the same order. In the live preview, tested =/-: 10→12→10, both examples in all variants, visible graphics of exactly the current result. The geometry and timeline did not change, OK was not pressed.

The 179 Python tests include regressions of vanishing internal edge staging, explicit budgeting, and preserving legacy precedence. This check confirms the described case, and not the completeness of all possible spatial cycles of an arbitrary BRep.


## Stable 1.0.0 - installation check and demo, 10/26/2026

Fusion 2706.1.14 on macOS creates a separate unsaved document: a plate with six holes and a capsular groove is divided into two precisely touching bodies. Three real PNGs from the viewport (1800 × 1100) are in `docs/images`: Select Similar by wall finds four identical full cylindrical faces; Select Chain by Edge finds six edges of a closed groove through two bodies; along the wall - six faces of the entire loop. Applying both circuits via OK gave exactly six initial entities, the temporary graphics were cleared.

Local package 1.0.0 was unpacked into a clean folder and added via GUI Scripts and Add-Ins → Script or add-in from device. The GUI displays version 1.0.0 and the path of the unpacked copy. The copy is running; according to the actual path of the loaded module, execution from the package is confirmed. Select Similar gave four faces in preview and after OK, Select Chain - six edges through two bodies in preview and after OK; There are no residual graphics. The test document is closed without saving; the original document, selection and working addition have been restored. After this, Fusion is freed up for other user tasks.

182 Python tests include release gate checks: tag and manifest version, presence of packages for all three OSes, checksum and ZIP identity. Release ZIP and SHA-256 are collected and published only by GitHub Actions by tag, local ZIP is used only for GUI verification of the installation. Windows Fusion native acceptance was not performed.

## Closed strip of faces — 10/28/2026

On the current user model, read-only BRep is performed: the selected expected rim consists of four faces. It was not in the catalog before the change; after the change, calling the updated adapter with one source face returned this set as the first of 18 options. The check is performed by calling adapter directly, without launching the Select Chain dialog, checking the highlight, or applying OK. The regression fixture contains a simplified topology of four faces and conditional dimensions without coordinates and model names.

Passed 185 Python tests, including rim priority for each of the four faces, retention of previous options, and failure when exceeding budget. Full acceptance of the UI in a separate unsaved document and Windows testing have not yet been carried out.

Rechecked in Fusion 2706.1.14 on macOS: the body was copied into a separate unsaved document, and the four faces were matched by centroid and area. After a normal restart of Selectra, the command showed the expected four faces of the first of 18 options, one by one; Magenta highlighting was checked visually and using links. The `=` and `-` keys switched 1 → 2 → 1 without accumulation. OK transferred exactly four expected faces, the temporary graphics were cleared. The test document is closed without saving, the original document and its previous selection are restored. Windows has not been tested.

Installation ZIP 1.0.1 is unpacked and connected via Scripts and Add-Ins. Checked the version and path of the loaded copy, the first outline of four faces on a separate copy of the model, OK and cleared the graphics. After verification, the test registration is deleted, the working copy is connected and launched; the original document and selection are restored. All 185 tests were also passed from the unpacked archive.
