<p align="center">
  <img src="docs/assets/monokl.png" alt="Monokl mirror" width="520">
</p>

# Monokl

A small, agent-agnostic research runner with durable evidence and explicit human approval.

> **Status:** early scaffold. `init`, `plan`, and `status` work. Retrieval and reasoning are planned, not implemented.

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
.venv/bin/pip install -e .

.venv/bin/monokl init ./research-run
.venv/bin/monokl plan ./research-run "What should we know about RNA JEPA?" \
  --include "primary papers" --exclude "uncited opinion" --max-sources 30
.venv/bin/monokl status ./research-run
```

## Target workflow

`scope → retrieve → group → approve → reason → audit → export`

Retrieved content is always untrusted. Runs are create-only. Private networks, credentials, persistent browser profiles, downloads, and retrieval-layer LLM calls are outside the first release.

## Plan

Development is split into eight MOZAK goals. Only the first is ready: the durable run ledger and validation foundation. Implementation requires separate owner approval.

- [Development plan](docs/development-plan.md)
- [Architecture](docs/architecture.md)
- [Security](docs/security.md)

## Development

```bash
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
```

MIT licensed.
