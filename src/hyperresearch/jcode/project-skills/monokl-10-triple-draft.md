---
name: monokl-10-triple-draft
description: Jcode project-local reference for upstream hyperresearch-10-triple-draft.
upstream_skill: hyperresearch-10-triple-draft.md
fail_closed: true
---

# monokl-10-triple-draft

This project-local Jcode skill is a thin reference for `hyperresearch-10-triple-draft.md`. It does not duplicate the upstream methodology.

1. Load the global `/monokl` skill.
2. Read `~/.jcode/skills/monokl/parity-map.json`.
3. Execute this stage through Jcode `swarm` and `todo` using the mapped role, dependencies, artifacts, and gate.
4. Use the packaged upstream skill body from `src/hyperresearch/skills/hyperresearch-10-triple-draft.md` as the methodological source.
5. Fail closed if required capabilities or declared artifacts are unavailable.
