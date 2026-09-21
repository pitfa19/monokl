# Packet 04: Package native Jcode skills

## Goal
Make the HPR workflow discoverable and operable as a native Jcode extension without duplicating the research methodology.

## Design
- One entry skill: `/monokl`.
- Reuse upstream HPR skill content as the single methodological source where practical.
- Add a thin Jcode-specific orchestration reference rather than rewriting every skill.
- Bundle scripts and references with paths resolved relative to each installed skill.

## Allowed changes
- Convert Claude-specific invocation text to Jcode skill and tool vocabulary.
- Add Jcode frontmatter and installation metadata.
- Add host capability declarations for browser, shell, swarm, todo, and background delivery.
- Add fail-closed messages when a required Jcode capability is unavailable.

## Do not
- Change the sequence or intent of the 16 research stages.
- Duplicate full skill bodies across multiple directories.
- Add Claude Code or Codex compatibility layers.

## Acceptance checks
1. A clean Jcode installation lists `/monokl`.
2. Skill loading resolves every bundled reference and script.
3. A static map accounts for every upstream skill and command.
4. No remaining instruction requires Claude-specific tools.
5. The skill teaches resume, inspection, and failure recovery.

## Stop conditions
Block if a stage cannot be represented through a Jcode skill without altering methodology. Record it for Packet 05 instead of hiding the gap.
