---
name: monokl-6-cross-locus-reconcile
description: Jcode project-local reference for upstream hyperresearch-6-cross-locus-reconcile.
upstream_skill: hyperresearch-6-cross-locus-reconcile.md
fail_closed: true
---

# monokl-6-cross-locus-reconcile

This project-local Jcode skill is a thin reference for `hyperresearch-6-cross-locus-reconcile.md`. It does not duplicate the upstream methodology.

1. Load the global `/monokl` skill.
2. Read `~/.jcode/skills/monokl/parity-map.json`.
3. Execute this stage through Jcode `swarm` and `todo` using the mapped role, dependencies, artifacts, and gate.
4. Use the packaged upstream skill body from `src/hyperresearch/skills/hyperresearch-6-cross-locus-reconcile.md` as the methodological source.
5. Fail closed if required capabilities or declared artifacts are unavailable.
