# Upstream provenance

Monokl v0.2 is derived from [HyperResearch](https://github.com/jordan-gibbs/hyperresearch).

- Upstream revision: `75b1ecfb2891184fad2cc1a2ddf9abe476f5b54c`
- Upstream package version at that revision: `0.11.1`
- Import method: exact Git tree checkout into the preserved Monokl repository
- Original license: MIT
- Original copyright: Jordan Gibbs, 2026
- Upstream baseline environment: Python 3.13.13
- Upstream baseline tests: 1,269 passed
- Upstream baseline lint: Ruff passed
- Upstream baseline type check: not green because optional third-party packages lack stubs and the installed NumPy stub emitted a Python 3.13 syntax diagnostic

## Mapping

Every path present in the pinned upstream tree was imported at the same path and byte content before Monokl-specific commits. Monokl-specific changes are reviewable as commits after the import commit. The preservation branch `archive/pre-hpr-rewrite` and annotated tag `pre-hpr-rewrite-2026-09-21` retain the earlier implementation.

## Product delta policy

Monokl changes only host integration, packaging, naming, installation, and documented licensing boundaries required for Jcode. Retrieval, vault, search, citation, contradiction, report, resume, and the 16-stage research methodology remain inherited from the pinned upstream implementation.
