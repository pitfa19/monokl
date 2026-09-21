---
name: monokl-16-readability-audit
description: Jcode project-local reference for upstream hyperresearch-16-readability-audit.
upstream_skill: hyperresearch-16-readability-audit.md
fail_closed: true
---

# monokl-16-readability-audit

This project-local Jcode skill is a thin reference for `hyperresearch-16-readability-audit.md`. It does not duplicate the upstream methodology.

1. Load the global `/monokl` skill.
2. Read `~/.jcode/skills/monokl/parity-map.json`.
3. Execute this stage through Jcode `swarm` and `todo` using the mapped role, dependencies, artifacts, and gate.
4. Use the packaged upstream skill body from `src/hyperresearch/skills/hyperresearch-16-readability-audit.md` as the methodological source.
5. Fail closed if required capabilities or declared artifacts are unavailable.
