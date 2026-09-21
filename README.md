# Monokl

**A small, agent-agnostic research runner with durable evidence and explicit human approval.**

Monokl turns a bounded question into a reviewable research run. Crawl4AI handles retrieval. Monokl owns scope, budgets, provenance, portable reasoning packets, citation checks, gaps, and approval boundaries.

> **Status:** early scaffold. `init`, `plan`, and `status` work today. Live crawling, agent adapters, synthesis, and MOZAK export are planned but not yet implemented.

## Why Monokl

Research workflows often bind retrieval, reasoning, and orchestration to one model or agent. Monokl separates them:

- **Crawl4AI retrieves** public web content behind a narrow adapter.
- **Any agent can reason** through versioned JSON task packets.
- **Monokl validates** ordering, hashes, locators, budgets, gaps, and approvals.
- **MOZAK can receive** validated proposal artifacts without automatically accepting them.

The goal is not autonomous truth. The goal is a small, resumable research ledger that a human, local model, hosted model, or coding agent can continue without changing the run contract.

## Try the implemented scaffold

```bash
git clone https://github.com/pitfa19/monokl.git
cd monokl
python -m venv .venv
.venv/bin/pip install -e .

.venv/bin/monokl init ./research-run
.venv/bin/monokl plan ./research-run "What should we know about RNA JEPA?" \
  --include "primary papers" \
  --exclude "uncited opinion" \
  --max-sources 30
.venv/bin/monokl status ./research-run
```

The commands emit machine-readable JSON. Writes are create-only, so repeating `init` or `plan` refuses to overwrite prior state.

## Target workflow

1. **Scope** the question, inclusions, exclusions, and budgets.
2. **Retrieve** source snapshots and hashes through Crawl4AI.
3. **Cluster** related sources for owner review.
4. **Reason** through provider-neutral task packets.
5. **Audit** every claim, locator, limitation, and unresolved gap.
6. **Export** a report, receipt, and proposal-only MOZAK artifact.

```text
question + boundaries
        |
        v
 immutable run ledger
        |
        +--> Crawl4AI retrieval --> source snapshots + hashes
        +--> portable task packets --> any agent, model, or human
        +--> owner approval gate
        +--> deterministic audit --> report + receipt + MOZAK proposal
```

## Safety boundary

- Retrieved content is untrusted data and cannot authorize actions.
- Public HTTP(S) is the intended default. Private, loopback, file, data, and custom schemes are refused.
- Crawl4AI's model-powered extraction is disabled in the retrieval layer.
- Browser profiles, cookies, credentials, proxies, and downloads are out of scope for the first release.
- Raw page bodies are temporary by default. Durable artifacts retain bounded evidence, locators, metadata, and hashes.
- Nothing becomes accepted project knowledge without an explicit owner decision.

See [Security decisions](docs/security.md) for the complete current boundary.

## What Monokl keeps small

Monokl borrows the useful research lifecycle from larger research systems without copying their full orchestration stack. The first releases intentionally omit embeddings, a permanent vault, autonomous source expansion, logged-in browsing, open-access recovery services, and provider-specific multi-agent machinery.

These features are added only when real pilots show a measured need.

## Roadmap

| Milestone | Outcome | State |
| --- | --- | --- |
| M0 | CLI, create-only run setup, scope and budget contracts | Implemented |
| M1 | Deterministic Crawl4AI retrieval with SSRF and budget controls | Planned |
| M2 | Manual and subprocess JSON reasoner adapters | Planned |
| M3 | Owner review, comparative synthesis, audit, MOZAK export | Planned |
| M4 | Measured extensions from real pilots | Deferred |

The first pilot will use the JEPA-RNA literature topic with 20 owner-supplied URLs and compare provenance completeness, source coverage, runtime, and operator effort against the earlier research workflow.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m unittest discover -s tests -v
```

Optional Crawl4AI setup for the future retrieval milestone:

```bash
.venv/bin/pip install -e '.[crawl,dev]'
crawl4ai-setup
crawl4ai-doctor
```

## Documentation

- [Architecture and implementation plan](docs/architecture.md)
- [Security decisions](docs/security.md)
- [README design and verification plan](docs/readme-plan.md)

## License

[MIT](LICENSE)
