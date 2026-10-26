# Contributing to Selectra

**English** · [Русский](CONTRIBUTING.ru.md)

Bug reports, selection scenarios, documentation improvements, and code changes are welcome. Start with the [user guide](docs/GUIDE.md) and check [existing issues](https://github.com/4FusionLab/Selectra/issues) for related discussions.

## Report a problem

Open an [issue](https://github.com/4FusionLab/Selectra/issues/new/choose). Include your operating system, full Fusion version, Selectra version or commit, selected examples, expected result, and actual result. Show which elements should be included and which are unwanted. Provide a minimal model you are allowed to publish, or instructions for building it.

A screenshot helps explain the highlight but does not replace geometry and reproduction steps. Remove personal information from logs. Use the [private channel](SECURITY.md) for vulnerabilities.

## Change the code

1. Fork the repository and create a branch.
2. Read [AGENTS.md](AGENTS.md). Preserve Search Scope, Chain across contact behavior, and the separation between the numeric core and the Fusion API.
3. For algorithm changes, check both a positive case and a similar-looking element that must be excluded.
4. Run the local checks:

   ```sh
   python -m unittest discover -s tests -v
   python -m compileall -q Selectra scripts tests
   python scripts/check_project.py
   python scripts/build.py
   ```

5. For UI, adapter, and lifecycle changes, run the relevant [native CAD checks](docs/VALIDATION.md). State explicitly which checks were not performed.
6. Update the documentation and Unreleased section in [CHANGELOG.md](CHANGELOG.md), then open a pull request.

Use Conventional Commits: `feat:`, `fix:`, `docs:`, `test:`, `ci:`, and `chore:`. Explain the resulting behavior and validation in the pull request. Run CAD checks in a separate unsaved document.

## Project conventions

- Maintain user-facing documentation in English and Russian. Update both versions when behavior changes. Discussions in either language are welcome; Fusion UI labels remain in English.
- The core receives numeric snapshots and does not import `adsk`. Runtime dependencies are the Python standard library and the Fusion API.
- Similarity scores are heuristics, not probabilities of user intent.
- Passing CI is not native CAD acceptance or proof of behavior in Fusion on Windows or macOS.
- Contributions are provided under `GPL-3.0-only`. Preserve authorship and compatible notices when using third-party code.
