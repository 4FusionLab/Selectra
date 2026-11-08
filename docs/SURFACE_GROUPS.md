# Logical surfaces from fragments

[Русская версия](SURFACE_GROUPS.ru.md)

`surface_groups.py` is an executable offline investigation of joining planar polygonal fragments. It is not yet connected to native selection: real STEP acceptance and the policy for selecting a complete logical surface remain separate work.

The input is a `BodySnapshot` of one body. Grouping requires graph connectivity of the source faces, coincident support planes within absolute tolerance, and a confirmed shared boundary segment. Internal shared segments are removed; collinear subdivisions and T-junctions are split first. The result retains the outer contour, holes, and all `source_keys`: references to original BRep faces are not replaced with a synthetic key.

The 1% relative similarity tolerance is not used to bridge gaps. Ambiguous joins, interior overlap, branching, or unsupported faces are retained in `rejected` with their source keys. If the budget is exceeded, `complete=False` and obtaining a complete selection is prohibited.

Synthetic rectangular fragments, a subdivided boundary, a frame with a hole, filling a hole, different planes, opposite normals, a rigid transform, overlap, self-intersection, point contact, and budgets have been checked. Command: `python3 -m unittest tests.test_surface_groups -v`.

This is not a general Boolean for arbitrary NURBS surfaces. Tessellation of different curved boundaries, real STEP imports, and transferring selection of a merged region into Fusion are not established here. Automatic merging in the product is currently disabled.
