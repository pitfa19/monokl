# Packet 01: Preserve current Monokl

## Goal
Make the current repository and v0.1.0 implementation recoverable before replacing `main`.

## Allowed changes
- Observe and record the exact clean repository revision.
- Create and push `archive/pre-hpr-rewrite` at that revision.
- Create and push annotated tag `pre-hpr-rewrite-2026-09-21`.
- Verify existing `v0.1.0` release assets and checksums remain downloadable.
- Add the pinned HyperResearch repository as `upstream` only after preservation verifies.

## Do not
- Delete or force-move `v0.1.0`.
- Rewrite existing Git history.
- Replace working-tree files in this packet.
- Begin the HPR import if the working tree is dirty or preservation refs disagree.

## Acceptance checks
1. Local and remote archive refs resolve to the same SHA.
2. The preservation tag resolves to that SHA and is annotated.
3. `v0.1.0` remains public with its assets.
4. The current test suite result and repository tree hash are recorded.
5. Upstream HEAD is exactly `75b1ecfb2891184fad2cc1a2ddf9abe476f5b54c`.

## Stop conditions
Stop before mutation if any current work is uncommitted, a preservation ref already exists at a different SHA, or remote verification fails.
