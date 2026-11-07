# 4FusionLab — release policy

This repository follows the organization-wide release contract. The **GitVersion.Tool version is pinned to 6.8.2**. This file defines eligibility; it does not independently start publication.

## Version identity

- `GitVersion.yml` plus Git history and existing immutable `v*` tags define the next version. Conventional commit messages `feat:`, `fix:`, `perf:` and breaking-change markers determine the intended bump.
- A Fusion manifest and filename of a distributable ZIP use the numeric **MAJOR.MINOR.PATCH** from GitVersion (not a PR branch identifier). An optional prerelease suffix belongs to the Git tag and GitHub Release metadata, not to Fusion's numeric manifest.
- A released artifact, its embedded manifest, checksum, Git tag and GitHub Release must describe the same product version. Do not retarget tags or replace assets of a published release.
- Product IDs, Fusion manifest compatibility metadata, packaging contents and release-note history must not change as a side effect of version calculation.

## Release gates

1. Development changes enter `main` through a reviewed PR with successful required tests; full Git history is fetched to calculate versions.
2. Every release requires a deliberately prepared, nonempty version-specific release note, recorded compatibility limitations and applicable native Fusion acceptance evidence. A passing Python workflow **is not** proof of native Fusion CAD testing.
3. Stable: `vMAJOR.MINOR.PATCH`, `prerelease=false`. Prerelease: `vMAJOR.MINOR.PATCH-IDENTIFIER`, `prerelease=true`; never mark a prerelease as Latest. Preserve each project's additional channel-specific gates.
4. Publish only the tested commit. Before publication, validate archive filenames, embedded manifest version and SHA-256; a failed gate must leave the existing release untouched.
5. GitHub Actions uses minimum necessary permissions; jobs and pull requests must not gain write permission merely to calculate a version.
6. Avoid opportunistic releases on a routine PR merge. When required release notes or project-specific approval/evidence is absent, skip publication safely rather than inventing notes or issuing an unintended version.
7. A broken release is corrected by a new patch version. Existing public tags, release notes and downloadable files remain immutable.

## Explicit release trigger (organization-wide)

- A product GitHub Release starts **only** when an immutable version tag `vMAJOR.MINOR.PATCH` (stable) or `vMAJOR.MINOR.PATCH-IDENTIFIER` (prerelease) is deliberately pushed for a tested commit reachable from `main`. Routine branch pushes, PR merges, and manual CI runs are not release triggers. Previously published historical channel classifications are unchanged.
- GitVersion.Tool **6.8.2** calculates the numeric `MajorMinorPatch`; the version tag must agree. Fusion manifests and ZIP filenames use the numeric version only, while the optional prerelease suffix belongs to the Git tag and GitHub Release metadata.
- Existing tests, ZIP/manifest and SHA-256 integrity gates, reviewed release notes, native CAD acceptance, platform limitations and project-specific controls still apply. An invalid explicit release attempt must fail safely without publishing.
- Never create or move version tags implicitly, retarget historical tags, overwrite published assets or mark prereleases Latest.
- Repositories without an approved distribution pipeline **do not publish** from tags. Enabling publishing requires a separate reviewed PR. Non-release deployments remain independent.

## Repository-specific publishing gate

Only an explicit version-tag push initiates publication, after all three OS CI packages pass byte-for-byte verification. Reviewed notes live in `docs/releases/X.Y.Z.md`. A routine main push or manual CI dispatch never publishes.
