# Packet 05: Translate subagents to Jcode swarm orchestration

## Goal
Run the HPR 16-stage pipeline through Jcode swarm primitives with equivalent role separation, review gates, and resumability.

## Design
- Map each upstream subagent to a named Jcode role or bounded task.
- Express ordering and dependencies with a Jcode task graph.
- Keep source retrieval, evidence extraction, critics, contradiction analysis, synthesis, and citation audit logically separate.
- Store durable stage artifacts in the HPR vault, not only in agent context.
- Make model routes configurable with safe defaults rather than embedding Claude model names.

## Required behavior
- The coordinator can start, inspect, resume, retry, and stop a run.
- Workers receive bounded objectives, allowed paths, inputs, expected outputs, and stop conditions.
- Reviewer roles cannot silently approve their own work.
- Failed or unavailable workers produce an explicit blocked stage.
- Web content remains untrusted and cannot authorize actions.

## Acceptance checks
1. A machine-readable parity map accounts for all 16 upstream agents/stages.
2. Dependency and gate ordering matches upstream.
3. Interruption after each major phase resumes at one exact next step.
4. Model substitution changes provenance only, not workflow authority.
5. A fresh reviewer can reproduce the stage inputs and outputs.

## Stop conditions
Do not collapse distinct adversarial or audit roles merely to reduce agent count. Block and document any Jcode capability gap.
