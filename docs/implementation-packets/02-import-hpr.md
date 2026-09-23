# Packet 02: Import the HyperResearch core

## Goal
Replace the custom Monokl implementation with the pinned HyperResearch core while keeping the delta reviewable and preserving attribution.

## Inputs
- Preserved repository SHA from Packet 01.
- HyperResearch commit `d329565d3fa0a74c8b5a80daa6c5e32e33c39799`.
- Upstream MIT license and copyright.

## Allowed changes
- Import upstream source, tests, skills, agents, templates, assets, and documentation.
- Rename package, commands, and user-facing product references where required for Monokl.
- Preserve an `UPSTREAM.md` record containing repository, commit, import method, and known delta.
- Preserve the MIT license and original copyright.
- Add an automated upstream-delta inventory.

## Do not
- Reimplement HPR retrieval, vault, search, citation, contradiction, report, or resume logic.
- Add Jcode orchestration yet.
- Modify methodology merely to simplify the port.

## Acceptance checks
1. Upstream tests run before modification and establish a baseline.
2. Imported code has a deterministic mapping to the pinned upstream tree.
3. License and attribution checks pass.
4. Every intentional deletion or modification appears in the delta inventory.
5. The package imports and CLI help run under supported Python versions.

## Stop conditions
Block if upstream tests cannot establish a baseline, imported files have unclear licensing, or the import requires large research-engine rewrites.
