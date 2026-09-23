# Code delta from HyperResearch

Monokl is a Jcode-focused fork of HyperResearch. Its imported baseline is upstream commit `d329565d3fa0a74c8b5a80daa6c5e32e33c39799`, package version `0.11.1`.

This document grounds the Monokl delta in repository paths. It distinguishes executable changes from generated skill payloads and project documentation.

## Runtime changes

| Change | Code paths | Behavior |
| --- | --- | --- |
| Product identity and version | `src/hyperresearch/__init__.py`, `pyproject.toml` | Publishes package and primary command as `monokl` version `0.2.0`, while retaining `hpr` and `hyperresearch` command aliases. |
| Jcode CLI routes | `src/hyperresearch/cli/__init__.py`, `src/hyperresearch/cli/jcode_cmd.py` | Adds `monokl jcode install`, `uninstall`, `routes`, and `doctor`. |
| Safe Jcode payload lifecycle | `src/hyperresearch/jcode/install.py` | Installs only declared global and project skill files, records SHA-256 ownership receipts, refuses symlinks, unowned files, drift, path escapes, and unsafe uninstall records. |
| Model routing and capability checks | `src/hyperresearch/jcode/routes.py` | Parses `MONOKL_MODEL_ROUTES_JSON`, rejects malformed or unknown stage routes, defaults to coordinator inheritance, and reports whether Jcode plus all installed payloads are ready. |
| Packaged Jcode contract | `src/hyperresearch/jcode/manifest.json`, `src/hyperresearch/jcode/maps/parity-map.json` | Declares the global skill, all 18 project stage skills, 19 upstream skill mappings, required Jcode capabilities, stage dependencies, artifacts, and review gates. |

Apart from the named identity and CLI integration files plus the new `src/hyperresearch/jcode/` subtree, no retrieval, vault, scholarly search, citation, contradiction, report, resume, or web-provider implementation was rewritten. Those subsystems remain the imported HyperResearch code.

## Skill translation

| Change | Code paths | Behavior |
| --- | --- | --- |
| Global entry skill | `src/hyperresearch/jcode/skills/monokl/SKILL.md` | Defines Jcode startup checks, model-route provenance, vocabulary translation, resume behavior, and fail-closed capability handling. |
| Full stage skills | `src/hyperresearch/jcode/project-skills/monokl-*.md` | Provides Jcode-hosted procedures for the 16 core stages and conditional stages 1.5 and 14.5. |
| Reproducible generation | `scripts/generate_jcode_skills.py` | Renders the Jcode stage payloads from the imported upstream skill sources and translates host-specific orchestration terms. |

The research gates and artifacts are inherited. The translation changes how Jcode coordinates work, not what counts as evidence or acceptance.

## Packaging, release, and disclosure

| Change | Code paths | Behavior |
| --- | --- | --- |
| Package metadata and payload inclusion | `pyproject.toml` | Renames the distribution, retains upstream attribution, includes Jcode payloads and license files, and exposes three compatible CLI names. |
| Publish safety | `.github/workflows/publish.yml` | Disables the imported upstream PyPI publishing workflow so Monokl cannot accidentally publish using upstream release policy. |
| Fork-facing documentation | `README.md`, `UPSTREAM.md`, `CHANGELOG.md`, `docs/migration-v020.md` | States fork provenance, install and migration paths, and compatibility boundaries. |
| Dependency licensing | `docs/pdf-backend-decision.md`, `docs/third-party-license-inventory.md`, `src/hyperresearch/licenses/` | Records the PyMuPDF AGPL-3.0-or-commercial boundary and upstream license provenance. |

## Project governance and tests

- `.mozak/` and `docs/implementation-packets/` contain Monokl planning and acceptance records. They do not alter runtime behavior.
- `tests/test_core/test_jcode_payload.py` tests parity coverage, safe install and uninstall, drift refusal, strict model routes, and doctor readiness.
- `assets/monokl.png` and the shortened `README.md` provide Monokl branding.

## Reproduce the delta

```bash
git diff --stat d329565d3fa0a74c8b5a80daa6c5e32e33c39799..HEAD
git diff --name-status d329565d3fa0a74c8b5a80daa6c5e32e33c39799..HEAD
git diff d329565d3fa0a74c8b5a80daa6c5e32e33c39799..HEAD -- src/hyperresearch pyproject.toml .github/workflows/publish.yml
```

The first two commands include documentation, MOZAK planning records, tests, and branding. The third narrows review to executable and packaging changes.
