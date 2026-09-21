# Monokl architecture and implementation plan

## Product boundary

Monokl is not an autonomous truth engine. It is a durable research run coordinator.

- Crawl4AI retrieves and normalizes web content.
- External agents or models reason through a versioned JSON protocol.
- Monokl validates ordering, provenance, budgets, citations, gaps, and owner decisions.
- MOZAK receives only validated proposal artifacts. It remains responsible for project knowledge and acceptance.

## Architecture

```text
question + boundaries
        |
        v
 immutable run ledger
        |
        +--> retrieval adapter --> Crawl4AI --> source snapshots + hashes
        |
        +--> cluster task packet --> any agent/model --> group proposal
        |
        +--> owner review gate
        |
        +--> reading/synthesis task packets --> any agent/model
        |
        +--> deterministic audit --> report + proposal-only MOZAK artifact
```

### Stable internal interfaces

1. `Retriever.retrieve(request) -> SourceSnapshot[]`
2. `Reasoner.run(TaskPacket) -> TaskResult`
3. `RunStore.append(Transition) -> Receipt`
4. `Auditor.validate(RunArtifacts) -> AuditReport`
5. `Exporter.render(RunArtifacts) -> report.md + run.json`

The first reasoner implementation is `manual`: Monokl writes a JSON packet and later imports a JSON result. A command adapter follows, so Jcode, Claude Code, Codex, an OpenAI script, Ollama, or another runner can participate without becoming a dependency of the core.

## What is retained from HyperResearch

- explicit question and source budgets
- durable resumable state
- source identity, content hashes, claims, locators, and gaps
- clustering and comparative synthesis
- human-readable reports plus machine-readable exports
- retrieval escalation recorded as a gap rather than silently hidden

## What is deferred

- a permanent knowledge vault and FTS index
- embeddings and ranking heuristics
- autonomous search expansion
- logged-in browser profiles
- open-access recovery services
- screenshots and media by default
- provider-specific multi-agent orchestration

## Crawl4AI boundary

Pin Crawl4AI and wrap only `AsyncWebCrawler.arun` and later `arun_many`. Disable LLM extraction in the retrieval layer. Use fixed browser/run configuration, explicit host allowlists, private-network denial, byte/page/time budgets, and capture:

- requested and final URL
- retrieval timestamp
- HTTP/status outcome
- Crawl4AI version and Monokl adapter version
- raw HTML hash when retained temporarily
- normalized Markdown hash
- title and metadata
- outgoing links selected for later review
- errors, redirects, and truncation

Retrieved text is untrusted data and never instruction-bearing.

## Phased plan

### Public documentation and release track

Every milestone also updates the public README from the implementation and focused architecture/security documents. The release check runs the documented quickstart, confirms that planned features remain labeled, reviews tracked files and history for secrets, and verifies that README edits did not silently remove unrelated guidance. The detailed workflow is in `docs/readme-plan.md`.

### M0: scaffold and contracts

Deliverables:
- package and CLI
- create-only run initialization
- scope and budget contract
- architecture and security decisions

Acceptance:
- init/plan/status run without optional crawling dependencies
- repeated writes fail closed
- invalid budgets fail

### M1: deterministic retrieval spike

Deliverables:
- narrow Crawl4AI adapter
- URL allow/deny policy including private-address refusal
- immutable source snapshot manifest
- fixture-driven tests plus one opt-in live crawl

Acceptance:
- same fixture produces identical normalized artifact hashes
- timeout, redirect, oversized page, crawl failure, and SSRF cases are represented explicitly
- no model API is invoked

### M2: provider-neutral reasoning protocol

Deliverables:
- versioned `TaskPacket` and `TaskResult`
- manual file adapter
- subprocess adapter using JSON on stdin/stdout
- cluster and reading task types

Acceptance:
- two different mock agents can complete the same packet
- malformed or stale results fail closed
- source claims require locators

### M3: review, synthesis, and MOZAK export

Deliverables:
- owner selection/approval artifact
- comparative group synthesis
- audit and gap report
- proposal-only MOZAK adapter output

Acceptance:
- no group proceeds without exact owner approval
- every report claim maps to source evidence
- MOZAK validates the exported run and accepts nothing automatically

### M4: measured extensions

Add only after real pilots demonstrate need: concurrency, adaptive/deep crawling, local SQLite index, OA recovery, authenticated profiles, or richer ranking.

## First pilot

Use the existing JEPA-RNA literature question. Limit to 20 owner-supplied URLs, single-page retrieval, no adaptive crawl, manual agent packets, and compare the output to the earlier HyperResearch run for provenance completeness, source coverage, runtime, and operator effort.
