# Changelog

[Русская версия](CHANGELOG.ru.md)

## 1.0.1 — 2026-10-28

- **Select Chain** finds closed strips of adjacent faces of one body with two simple boundaries. A narrow rim takes priority, including transitions along inclined faces.
- When the starting example changes, the catalog is rebuilt; previous contour options are retained. Enumeration is budget-limited.
- Preview, option switching, and application of a four-face rim were tested in Fusion on macOS on a separate copy of a model. 185 Python tests; native CAD acceptance on Windows was not performed.

## 1.0.0 — 2026-10-26

The first stable release of Selectra for Autodesk Fusion.

- **Select Similar**: similar BRep edges, faces, and connected groups from one or more examples, refined using Examples, Exclude, and Match.
- Shape and size take priority, then position: example planes, parallel planes, then others.
- **Search Scope**: This Body, This Component (default, including nested hierarchy), All Components.
- **Select Chain**: separate closed edge contours and wall chains. Each option passes through every example and replaces the previous one.
- Boundaries of smooth groups and their intermediate connected parts; original Split Body contours are preserved.
- **Chain across contact**, on by default: transition across full exact face contact without changing source bodies. Gaps, partial contact, and volume intersections are not connected.
- **PgUp/PgDown** and **=/-**, native slider, Magenta preview before OK, and restoration of the original selection on Cancel.
- English and Russian documentation, demonstration images, reproducible ZIP and SHA-256; stable releases were built and published by tag via GitHub Actions.

Validation: 182 Python tests; build and CI on macOS, Windows, and Ubuntu. Native CAD scenarios were checked in Fusion on macOS; native Windows acceptance was not separately performed. See the [validation report](docs/VALIDATION.md).
