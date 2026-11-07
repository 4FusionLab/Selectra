# Publishing Selectra

[Русская версия](PUBLISHING.ru.md)

Selectra uses GitVersion 6.8.2 as the source of its numeric `X.Y.Z` release identity. The current workflow publishes stable releases from eligible pushes to `main`; it creates the immutable `vX.Y.Z` tag automatically. Do not create or move release tags manually. The version embedded in the Fusion manifest inside the published ZIP and the ZIP name must match GitVersion. GitHub Actions alone builds and publishes release assets.

## Push and pull request checks

CI checks Python 3.14 on Ubuntu, macOS and Windows: compilation, unit tests, public metadata and documents, manifest, and ZIP. Third-party Actions are pinned to full commit SHAs; Dependabot proposes updates in separate PRs.

Each OS uploads a `Selectra-package-Linux`, `Selectra-package-macOS`, or `Selectra-package-Windows` artifact containing a ZIP and SHA-256. The workflow does not run Fusion and does not replace CAD acceptance.

## Preparing a stable release

1. Run CAD scenarios on the platforms being claimed and record Fusion/OS versions, checks performed and limitations in [the validation report](VALIDATION.md). Distinguish automated checks from native acceptance.
2. Resolve the version using GitVersion and update the README, changelog and, where applicable, both `docs/releases/X.Y.Z.md` / `X.Y.Z.ru.md`. Capture real Fusion demo images. CI stamps GitVersion into the manifest **inside the ZIP**, without changing the source manifest in the repository.
3. Verify installation of the extracted ZIP through the Fusion GUI. A local build is for verification, not upload to a Release.
4. Run local checks and wait for green CI for the reviewed commit, then merge it to `main`. The release job runs only on a `main` push with eligible shipped changes under `.github/release-paths.txt`. A docs-only push may retry an earlier missed runtime release; it does not create a release independently. PR and manual workflow runs do not publish.
5. After the three OS jobs pass, the release job downloads all three packages, validates manifest and SHA-256, and requires byte-identical archives. It uses reviewed version-specific notes when available; otherwise the shared action generates notes from Git history.
6. `scripts/publish_release.py` creates a draft, uploads the ZIP and checksum from CI, verifies server digests, and publishes it. The current workflow uses the stable channel and marks the release Latest. GitHub Actions supplies a token only to the publishing job; the script rejects local publication.
7. Read published metadata, download the ZIP and SHA-256 from the release page, and verify contents and checksum. The description automatically includes the CI link and commit.

Archives are named `Selectra-X.Y.Z.zip`. Publication is blocked on mismatched GitVersion, manifest, package bytes or checksum. A published release is immutable; retries do not replace different published assets. See the [release policy](../.github/RELEASE_POLICY.md) for recovery and eligibility details.
