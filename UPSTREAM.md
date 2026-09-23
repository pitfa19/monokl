# Upstream provenance

Monokl v0.2 is derived from [HyperResearch](https://github.com/jordan-gibbs/hyperresearch).

- Upstream revision: `d329565d3fa0a74c8b5a80daa6c5e32e33c39799`
- Upstream package version at that revision: `0.11.1`
- Import method: exact Git tree checkout into the preserved Monokl repository
- Original license: MIT
- Original copyright: Jordan Gibbs, 2026
- Integrated Monokl baseline environment: Python 3.13.13
- Integrated Monokl tests at this pin: 1,325 passed
- Integrated Monokl lint at this pin: Ruff passed
- Type check: not used as an acceptance gate because optional third-party packages lack stubs and the installed NumPy stub emits a Python 3.13 syntax diagnostic

## Mapping

Every path present in the pinned upstream tree was imported at the same path and byte content before Monokl-specific commits. Monokl-specific changes are reviewable as commits after the import commit. The preservation branch `archive/pre-hpr-rewrite` and annotated tag `pre-hpr-rewrite-2026-09-21` retain the earlier implementation.

The code-level delta from this pinned revision is catalogued in `docs/code-delta-from-hyperresearch.md`. Reproduce the inventory with:

```bash
git diff --name-status d329565d3fa0a74c8b5a80daa6c5e32e33c39799..HEAD
```

## Product delta policy

Monokl changes only host integration, packaging, naming, installation, and documented licensing boundaries required for Jcode. Retrieval, vault, search, citation, contradiction, report, resume, and the 16-stage research methodology remain inherited from the pinned upstream implementation.
