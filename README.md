<p align="center">
  <img src="docs/assets/monokl.png" alt="Monokl mirror" width="520">
</p>

# Monokl

A small, agent-agnostic research runner with durable evidence and explicit human approval.

> **Status:** ledger and bounded retrieval work. Reasoning, grouping, synthesis, and export are not implemented yet.

## Why

Monokl separates research state from the agent doing the reasoning:

- Crawl4AI retrieves bounded public web content.
- Any agent, model, or human can process versioned JSON task packets.
- Monokl owns provenance, hashes, evidence, gaps, receipts, and approvals.
- MOZAK receives proposal-only exports and accepts nothing automatically.

## Try it

```bash
git clone https://github.com/pitfa19/monokl.git
cd monokl
python -m venv .venv
.venv/bin/pip install -e '.[crawl]'
PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright" .venv/bin/playwright install chromium

.venv/bin/monokl init ./research-run
.venv/bin/monokl plan ./research-run "What evidence answers this question?" \
  --include "public primary sources" --exclude "uncited opinion" --max-sources 30
.venv/bin/monokl retrieve ./research-run https://example.com \
  --allowed-host example.com --crawl4ai
.venv/bin/monokl validate ./research-run
.venv/bin/monokl resume ./research-run
```

The Crawl4AI path fails closed unless it can run in a user cgroup with a scrubbed environment, fixed browser policy, public HTTP(S)-only routing, and explicit CPU, memory, task, file, normalized-output byte, redirect, and time bounds. The byte limit bounds the retained normalized result, not upstream transfer size. See [Agent handoff](docs/agent-handoff.md) for the exact MOZAK-connected workflow.

## Target workflow

`scope → retrieve → group → approve → reason → audit → export`

Retrieved content is always untrusted. Runs are create-only. Private networks, credentials, persistent browser profiles, downloads, and retrieval-layer LLM calls are outside the first release.

## Plan

Development is split into MOZAK goals. The durable ledger and retrieval goals are implemented locally. Later goals require separate approval.

- [Development plan](docs/development-plan.md)
- [Architecture](docs/architecture.md)
- [Security](docs/security.md)

## Development

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
```

MIT licensed.
