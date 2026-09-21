# Packet 07: Demonstrate parity

## Goal
Show that Jcode Monokl preserves the useful HyperResearch behavior before publishing it.

## Test layers
1. Run the complete upstream unit and integration suite.
2. Run static skill, agent, command, and artifact parity inventories.
3. Run deterministic fixture workflows without network access.
4. Run one bounded public-source acceptance workflow through the installed Jcode extension.
5. Exercise interruption, resume, retry, blocked worker, malformed source, citation failure, and missing-provider paths.

## Observable acceptance
- All 16 logical stages execute or explicitly block for a documented external reason.
- Expected vault artifacts are created and searchable.
- Every supported claim has a resolvable citation.
- Contradictions, gaps, and unsupported claims remain visible.
- Critics and final citation audit execute as separate gates.
- No Claude Code executable, account, skill, or environment variable is required.
- The JEPA-RNA topic is not used as a fixture.

## Evidence
Publish a parity matrix, test logs, fixture hashes, installed-run receipt, limitations, and any accepted deviations.

## Stop conditions
Do not treat unit tests or static inspection as end-user parity. Do not release while any load-bearing stage is absent or silently degraded.
