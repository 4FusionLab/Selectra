# Selectra

[Русская версия](AGENTS.ru.md)

Selectra simplifies selecting Autodesk Fusion BRep edges and faces by example.

## Work

- Communicate and plan, including in plan mode, in Russian. Write documents in English and maintain separate Russian versions of documentation; intermediate working notes do not require translation. UI labels are English, using Fusion terminology.
- For questions about libraries, SDKs, APIs, CLI tools and cloud services use Context7: first resolve-library-id, then query-docs for the specific question. If Fusion coverage is incomplete, check official Autodesk documentation and installed API definitions.
- Check Git before changes and preserve others' work. Branches use `codex/…`.
- Search Scope defines the area: This Body is the source body of the selected instance; This Component is the first example's component and nested hierarchy, by default; All Components is the entire visible assembly. This Component excludes neighboring instances of the same definition. Examples and exclusions are available within the chosen scope; narrowing past explicit examples is rejected until the user removes them.
- Do not create a web demo. Test the core in Python and validate the interface in Fusion after user authorization.
- PgUp/PgDown and aliases =/- change the ranked range of entities of the selected type in the current scope. The wheel remains Fusion navigation; graph adjacency is a separate operation.
- Before OK, display the result with stable Magenta highlighting. There is no separate Preview field. The canonical workflow is `docs/UX.md`.
- For the browser prefer connected DevTools or a specific tab and narrow requests. Use Computer Use for native UI, visual checks and unavailable elements. Verify actual connectivity; coordinate remote-debugging activation and browser restart separately.

## Architecture and product

- `Selectra/matching.py` is the pure deterministic kernel on numeric snapshots, without `adsk`. Units: cm, cm², rad.
- `ranking.py`, `snapshot.py`, `selection.py` provide shared ranking, body snapshot and range/refinement state; algorithm details are in `docs/RANKING.md`.
- `highlight.py` provides the temporary Magenta overlay in executePreview; valid graphics are reused and groups are cleared when the command ends.
- `Selectra/fusion_adapter.py` reads BRep and checks scope; references to live objects belong to one command session.
- `Selectra/Selectra.py` implements the native command, preview and event lifecycle. The add-in changes selection while preserving geometry and timeline.
- The default entry point is one `Select Similar`. Criteria are inferred from examples; refinements are shown when needed. Ranking is a heuristic, not a probability of user intent.
- For UX and algorithm changes read `docs/PRODUCT.md`; API capabilities and limitations are in `docs/API_RESEARCH.md`; sequencing and completion criteria are in `PLAN.md`.
- The adapter preserves proxy/assemblyContext and distinguishes instances; numeric snapshots and temporary graphics are converted to world coordinates. tempId is namespaced by body when combining; topology and wall pairs remain inside the body. Check revisions of all bodies in scope and occurrence transforms before preview and delayed OK.
- Use the Python standard library supplied with Fusion. Do not use Preview API in the distributed product.

## Verification

- Test the core: `python3 -m unittest discover -s tests -v`.
- For public packaging also run `python3 scripts/check_project.py` and `python3 scripts/build.py`. Preserve PolyForm Noncommercial 1.0.0 and the corresponding SPDX headers. Before release read `docs/PUBLISHING.md`.
- UI and adapter require real Fusion tests according to `docs/VALIDATION.md`. Use one CAD session and a separate unsaved document; leave the user's active document untouched.
- Distinguish unit tests and API definition checks from live CAD acceptance. See `docs/VALIDATION.md` for exact coverage; macOS results do not establish Windows behavior.
- On command completion check document, current command and object validity before delayed transfer of selection. Retain event handlers until session end and release them on stop.

## Shared 4FusionLab engineering contract

- Organization rules and shared CI components are documented in [4FusionLab/.github](https://github.com/4FusionLab/.github/blob/main/AGENTS.md) and [Release Platform](https://github.com/4FusionLab/.github/blob/main/RELEASE_PLATFORM.md). These product-specific rules apply in addition.
- Before edits inspect existing Git changes, documentation, automated checks and Autodesk Fusion compatibility. Do not delete user data or change existing command IDs, manifest UUID or add-in structure without a migration plan.
- Use Conventional Commits for ordinary development; a small PR with CI is preferred, though direct push to `main` is allowed by repository policy. Do not rewrite history or modify published tags/artifacts.
- **Automatic releases occur only for shipped product changes**: push or merge to `main` → check `.github/release-paths.txt` → tests → GitVersion 6.8.2 → new immutable tag and GitHub Release. Do not create tags manually; changes to README, documentation, tests, workflows or `AGENTS.md` must not independently publish a release.
- Pin shared GitHub Actions to the **exact SHA** of a reviewed `4FusionLab/.github` commit, not `@main`. Package, manifest, SHA-256, release notes and version must agree; do not overwrite existing releases.
- Passing unit tests and building a ZIP **does not prove** operation in installed Autodesk Fusion. Record actual CAD acceptance and OS separately for Fusion API and UI changes.
- Preserve existing English and Russian documentation, licenses, limitations and project-specific workflows. Do not publish secrets, personal CAD documents, tokens or local-machine artifacts.
