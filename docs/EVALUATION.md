# Evaluation of Selectra engineering iterations

English | [Русский](EVALUATION.ru.md)

## Method

The baseline is the unchanged `ranking.py` algorithm from `c5ac432`, saved in `evaluation/baseline_c5ac432.py`. Only the import path for the pure `Tolerance` and `_angle` types differs. The new implementation is compared with it on the same `evaluation/corpus.py` corpus.

The corpus is **synthetic**, with no user models. Task labels cover equal length/axis; a second example; exclusion; an indistinguishable exclusion; U/T contours with equal area, perimeter and side count; translation/rotation/reflection; a shifted hole; the sequence analogue → its own wall → analogue's wall; an empty cavity; and nearby size families.

Command: `python3 scripts/evaluate_selection.py --json artifacts/evaluation/results.json`.

The measurements are:

- Exact match between the first proposal and the target set. For the multi-step wall scenario, the first set is compared with the first checkpoint, and reachability and steps with the final target.
- Precision/recall for added candidates only; explicit examples do not provide free correct answers. When both the correct and predicted additions are empty, both metrics equal 1.
- Reachability of the target set by some nested range and the minimum number of PgUp/PgDown steps from the automatic range. Unreachable targets are reported explicitly, not replaced by an action count.
- Separate intermediate sets in the wall scenario.
- Cost of feedback already specified: a second example and Exclude are separate actions. These are manual scenarios; user strategy optimality is not claimed.
- Preservation of all groups under coordinate transformations, reflection, example reordering and identifier replacement. The camera is not part of the snapshot; UI stability is checked separately.
- Median pure Python ranking time. BRep reading, highlighting, UI latency and Fusion are **not measured** here.

## Results

Preliminary offline run on 2026-10-25 after integrating the `Descriptor.contours` and `BodySnapshot.wall_pairs` contracts:

| Corpus / algorithm | Exact first set | Target reachability | Precision / recall of added candidates | Invariance |
| --- | --- | --- | --- | --- |
| Development, baseline | 5/11 | 7/11 | 0.697 / 0.758 | 11/11 |
| Development, current | 11/11 | 11/11 | 1.000 / 1.000 | 11/11 |
| Additional challenging tasks, baseline | 2/6 | 4/6 | 0.500 / 0.750 | 6/6 |
| Additional challenging tasks, current | 5/6 | 6/6 | 1.000 / 0.917 | 6/6 |

Additional tasks (`holdout_tasks`) were labelled after the initial integration and are reported separately: rotating a profile into another coordinate plane, a curved distractor, an unknown candidate contour, an unknown example contour, excluding a congruent analogue, and two different recurring families with a third excluded profile. These are additional manually designed examples, not a statistically independent market evaluation.

The first additional run found two limitations. The missing example contour case was fixed: automatic mode retains the examples and reports ambiguity instead of including a false shape on a scalar tie. A later check of multiple user regions introduced the union of verified families for disconnected planar examples. The two-family task now produces the exact first set; its label was retained. Final numbers need to be measured again after further changes and CAD acceptance.

The wall scenario in the current algorithm passes the three specified sets in order; two PgUp steps are needed from the first proposal to the final target. The baseline cannot express the intermediate pair separately from other interior faces with equal scalar features. Exceeding the contour budget (513 points) was separately verified as a controlled failure without partial ranking.

After geometric integration was completed, the final counts did not change. The sum of median pure analysis times across 11 small tasks was approximately 0.34 ms for the baseline and 2.54 ms for the current algorithm (five repeats per task). This is a local microbenchmark, not command latency or a scalability measure. A machine-readable report with source hashes is saved locally in the ignored `artifacts/evaluation/results.json`.

## Native validation and practical value

On a separate synthetic CAD part, the first proposal and both subsequent wall-pair levels, actual PgUp/PgDown, OK/Cancel, scope preservation, absence of residual graphics and an unchanged model were confirmed. Two wall examples immediately produced both corresponding pairs; two adjacent examples produced geometrically repeated groups. The full protocol and reproducible fixture are in [VALIDATION.md](VALIDATION.md).

Separated first-run times: BRep reading 2.37 ms, topology 0.58 ms, relations/material 1.77 ms, pure analysis 0.48 ms, graphics 70.16 ms. For a repeated group, analysis was 1.40 ms and graphics 91.53 ms. Graphics were the main cost for this small part. Changing the range uses cached data without rereading BRep.

An additional read-only smoke test on an open 39-face part measured 149.67 ms for full reading, 9.22 ms for analysis and six ranges. This checks for scope/reading regressions; it does not label proposal correctness on a user task. Exact user geometry was not saved in the corpus.

Review found that five point-sampling depths do not prove material continuity. A native experiment with a narrow cavity between samples reproduced a false confirmation; added BRep-ray intersections along the full test path eliminated it. Paths across the overlap remain discrete, so the entire wall volume is not proven.

A repeated group is checked using one common 3D transformation. A false repeat with matching end shapes and thickness but different tangential offset is rejected by a regression test. When the budget is exceeded or data is unknown, analysis is explicitly incomplete and a partial set is not applied.

Value relative to the baseline is established for the narrow corpus: correct shape with equal scalar features and walls expressible in three levels. User time on real tasks has not yet been measured. The 11/11 result cannot be generalized to arbitrary CAD models.

## Limitations and further checks

Assembly scopes and +/- aliases were added in a separate iteration. On a native assembly of 10 visible bodies, the first sets contained 2 / 6 / 20 entities for This Body / This Component with children / All Components. World-space highlighting geometry matched the original proxies; OK preserved the exact entities. On a user project, after fixing an assemblyContext failure and optimizing optional relations, a full read of the last visibility snapshot took about 0.50 s for 338 faces and analysis took 0.074 s. This is a separate functionality check, not a new corpus accuracy label. See VALIDATION for details.

The synthetic corpus is small and cannot estimate how common user tasks are. Labelled real parts and STEP files, repeated polyhedral groups, freeform surfaces, large bodies and Windows CAD are needed. Discrete native material evidence is not strict volumetric proof of a wall. Targets that cannot be expressed by a range remain defects or limitations of the intent model even if first-set precision improves.

After plane ordering was introduced on 2026-10-25, development remained at 11/11, holdout at 4/6 exact first sets and 6/6 reachable targets, with 6/6 invariance. The historical `holdout-spatial-rotation` label expected immediate union of identical shapes in different planes; the new requirement deliberately separates them, so that target is now reached in one step. The label was retained without fitting it to the result. Ten separate plane tests check the new contract, including dimensions, exclusions, multiple examples, unknown data and coordinate transformations. Native confirmation: This Component 4→8→10, All Components 4→8→20 circular edges; exact transfer on OK and graphics cleanup were checked separately; see VALIDATION.

After fixing multiple regions, development was 11/11, holdout 5/6 first sets and 6/6 reachable targets, with added-candidate precision/recall of 1.000/0.917. `holdout-two-shape-families` now passes immediately; spatial rotation remains an intentional separate step under the plane policy. On a local numeric snapshot of the two current shaped faces of a user part, the first set changed from 26 to 6; analysis took about 0.37 s. The snapshot is kept locally only; user geometry is not included in the public corpus.

The 2026-10-26 curved-groove iteration does not change the old labels: development 11/11, holdout 5/6 first sets and 6/6 reachable targets. Seven additional group regressions and a native 12→18→12 sequence on an unsaved copy of selected grooves were performed, with exact OK and unchanged original bodies. The old corpus numbers are not an accuracy evaluation of the new NURBS group class.
