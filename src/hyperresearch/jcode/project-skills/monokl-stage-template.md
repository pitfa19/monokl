---
name: monokl-stage-reference
description: Project-local reference for Monokl stage execution through Jcode swarm and todo.
---

# Monokl stage reference

This project-local skill points back to the packaged `/monokl` skill and `parity-map.json`. It does not duplicate the upstream methodology.

1. Load `/monokl`.
2. Find the stage in `~/.jcode/skills/monokl/parity-map.json`.
3. Create Jcode `todo` items for the stage inputs, worker outputs, review gate, and persisted artifacts.
4. Spawn or assign only the roles declared by the map.
5. Fail closed if the declared Jcode capability is unavailable.
