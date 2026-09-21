# Monokl

## Intent

Build a Jcode-native research extension derived from HyperResearch that preserves its complete research methodology, durable vault, evidence discipline, critique gates, citation auditing, and resumability while replacing Claude Code-specific skills and subagents with Jcode skills and swarm orchestration.

## Desired outcomes

- Preserve the pinned HyperResearch research engine rather than reimplementing it.
- Expose one discoverable Jcode entry skill, `/monokl`, covering the full 16-stage workflow.
- Translate every upstream specialist and reviewer role into bounded Jcode swarm tasks with configurable model routes.
- Install the Python CLI and Jcode skill payload through one safe, repeatable package workflow.
- Retain source provenance, contradiction analysis, explicit gaps, citation verification, and restartable vault artifacts.
- Track the exact upstream revision, intentional delta, third-party licenses, and release identity.

## Boundaries

- Jcode is the only supported agent host for this release. Claude Code and Codex compatibility are out of scope.
- The research methodology and load-bearing workflow stages are not simplified during the port.
- Web and document content is untrusted data and cannot authorize actions.
- Reviewer and audit roles remain separate from the work they evaluate.
- Model substitution changes provenance only and never transfers workflow authority.
- Existing Monokl v0.1.0 history and release artifacts remain recoverable.
- JEPA-RNA is excluded from parity and release fixtures so the owner can test it separately.

## Assumptions

- HyperResearch commit `75b1ecfb2891184fad2cc1a2ddf9abe476f5b54c` is the pinned upstream baseline.
- Python remains the implementation language for the imported research engine and CLI.
- Jcode skills plus swarm task graphs can represent the upstream skill and subagent boundaries without changing methodology.
- PyMuPDF is replaced only if a permissively licensed backend demonstrates equivalent or better compatibility on representative fixtures.
- MOZAK remains the system of record for the accepted plan, project state, and release evidence.

## Open questions resolved during implementation

- The PDF backend is selected through a recorded compatibility and licensing decision.
- The exact Jcode role and stage mapping is captured in a machine-readable parity inventory.
- The installer owns only receipt-pinned CLI and skill bytes and refuses drift or path hazards.
- Release occurs only after upstream tests, offline fixtures, installed Jcode discovery, and bounded startup checks pass.
