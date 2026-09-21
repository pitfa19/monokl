# Monokl development plan v1

## Authority and start gate

This is a development proposal, not authorization to implement it. Development starts only after the owner explicitly approves `goal-ledger` from the MOZAK goal DAG. Later goals become ready only when their declared dependencies have completed and their acceptance evidence is recorded.

## Product outcome

Monokl will be a small local-first CLI that turns a bounded research question into a resumable, auditable run. Crawl4AI performs bounded retrieval. Agents, models, or humans interact through provider-neutral JSON task packets. Monokl remains the authority for workflow order, immutable artifacts, provenance, evidence locators, gaps, receipts, and owner approvals.

## Architecture boundaries

- **Core:** Python contracts, canonical JSON, hashing, append-only transitions, validators, receipts, and resume guidance.
- **Retrieval:** a narrow Crawl4AI adapter with Monokl-owned URL policy, budgets, deterministic normalization metadata, and cache identity.
- **Reasoning:** versioned task/result contracts with manual-file and subprocess JSON adapters. Provider-specific clients remain outside core.
- **Workflow:** scope, retrieve, inventory, group, approve, extract, synthesize, audit, export.
- **Integration:** MOZAK receives validated proposal-only artifacts. A generated skill may teach usage later, but it is not the product runtime.

## Goal plan

### 1. `goal-ledger` — Durable run ledger and validation foundation

Deliver:
- versioned run, transition, artifact-reference, and validation-error contracts
- canonical JSON serialization and SHA-256 identity
- atomic create-only writes and append-only transition rules
- `validate` and `resume` commands
- schema migration policy that never mutates prior evidence in place

Acceptance:
- interrupted and partially written transitions fail closed
- repeated writes cannot overwrite evidence
- `resume` identifies exactly one next phase or an explicit blocked state
- validation detects missing artifacts, hash drift, invalid order, unknown fields, and stale results
- tests cover clean runs, interruptions, symlinks, traversal attempts, and concurrent-write refusal

### 2. `goal-retrieval` — Safe deterministic Crawl4AI adapter

Deliver:
- optional pinned Crawl4AI integration behind `Retriever`
- public HTTP(S)-only policy with DNS/IP checks before and after redirects
- host, page, byte, redirect, and time budgets
- immutable source snapshot manifests and content hashes
- Monokl-owned deterministic cache keys and declared truncation/error records
- isolated browser process policy with explicit network boundaries and resource limits

Acceptance:
- loopback, private, link-local, file, data, custom schemes, and redirect-to-private targets are refused
- timeout, redirect loop, oversized content, HTTP failure, malformed page, and partial crawl become explicit artifacts
- identical fixtures produce identical durable metadata and hashes
- no LLM API, credential, persistent profile, proxy, download, or arbitrary JavaScript path is invoked
- browser execution cannot reach loopback, private services, local files, or undeclared hosts, including after DNS resolution and redirects
- browser process, child-process, memory, CPU, and temporary-storage limits are enforced and observable
- one opt-in public-page acceptance crawl passes after fixture tests

### 3. `goal-reasoning-protocol` — Agent-neutral task and result protocol

Deliver:
- versioned `TaskPacket` and `TaskResult` contracts
- manual export/import adapter
- subprocess adapter using JSON stdin/stdout, timeout, output-size limit, and no shell interpolation
- task types for grouping, source reading, claim extraction, contradiction checks, and comparative synthesis
- provider/model/tool metadata recorded only as provenance

Acceptance:
- two independent mock reasoners complete identical packets
- malformed JSON, unknown fields, stale hashes, missing locators, timeout, nonzero exit, and oversized output fail closed
- task payloads distinguish untrusted source text from trusted workflow instructions
- core tests require no model credentials or network access

### 4. `goal-inventory-grouping` — Source inventory, deduplication, and owner-review groups

Deliver:
- source inventory with canonical URL, retrieval lineage, duplicate relationships, and coverage gaps
- deterministic exact/content duplicate handling
- provider-neutral clustering task packet for semantic grouping
- human-readable group proposal with included and excluded sources
- exact owner approval artifact pinning run, inventory, groups, and revision

Acceptance:
- every source is accounted for exactly once as included, excluded, duplicate, failed, or deferred
- grouping results cannot introduce unknown sources or silently omit retrieved sources
- stale task results and approvals fail closed
- no source proceeds to reading or synthesis without exact group approval

### 5. `goal-evidence-synthesis` — Evidence, claims, gaps, synthesis, and audit

Deliver:
- claim records with source identifiers, locators, verification state, limitations, and inference labels
- contradiction and unresolved-gap inventory
- group synthesis and cross-group comparison artifacts
- deterministic audit linking every report claim to evidence or marking it unsupported
- patch-only correction workflow preserving prior artifacts

Acceptance:
- source claims require resolvable locators and pinned source hashes
- inferences are never represented as source claims
- unsupported, conflicting, or coverage-limited conclusions remain visible
- audit fails on orphan claims, missing evidence, altered source hashes, or unreported gaps
- report regeneration cannot silently remove limitations or change cited evidence

### 6. `goal-export-integration` — Reports, receipts, resume, and MOZAK proposal export

Deliver:
- `report.md`, `evidence.json`, `gaps.json`, `receipt.json`, and machine-readable run export
- MOZAK adapter output matching a supported research normalization contract
- end-to-end `status`, `validate`, and `resume` guidance
- provenance receipt recording inputs, versions, hashes, validations, and approval state

Acceptance:
- MOZAK validates the exported run while accepting nothing automatically
- receipts reproduce artifact identity and detect drift
- report claims trace to evidence through machine-readable identifiers
- a complete run can move between humans, Claude, OpenAI, local models, and coding agents without changing the core contract

### 7. `goal-jepa-rna-pilot` — Real JEPA-RNA pilot and HyperResearch comparison

Deliver:
- one bounded run using 20 owner-supplied JEPA-RNA URLs
- single-page retrieval only, no adaptive crawling
- manually reviewed grouping and agent-neutral reasoning packets
- comparison against the earlier HyperResearch workflow

Acceptance:
- measure source coverage, locator completeness, unsupported claims, runtime, operator actions, and resume behavior
- exercise crawl failures, duplicates, contradictory papers, unavailable full text, and source updates
- use deterministic local fixtures for redirects, failures, duplicates, truncation, and unavailable content instead of relying on owner URLs to exhibit those cases
- identify which deferred capabilities are actually needed
- do not claim research-quality superiority without comparable evidence

### 8. `goal-hardening-private-beta` — Packaging, security review, documentation, and private beta

Deliver:
- reproducible package build and locked dependency policy
- supported Python/OS matrix and installation checks
- security threat review and dependency/license inventory
- CLI reference, operator guide, architecture, troubleshooting, and release checklist
- private beta tag only after all preceding acceptance checks pass

Acceptance:
- clean installation and complete workflow pass in a fresh environment
- static checks, tests, package inspection, secret scan, and dependency review pass
- documentation labels experimental and unsupported behavior accurately
- no repository visibility change, publication, or public release occurs without separate owner approval

## Deferred until pilot evidence

- adaptive or deep crawling
- authenticated browsing, cookies, proxies, or downloads
- embeddings, vector search, or permanent full-text vault
- automatic open-access recovery
- automatic source-quality rankings
- provider-specific orchestration or hidden multi-agent behavior
- automatic promotion into MOZAK knowledge

## Development approval requested

Approve only the first ready goal: `goal-ledger`, version 1. Approval authorizes implementation and tests for that bounded goal. It does not authorize later goals, publication, repository visibility changes, external model spending, authenticated browsing, or promotion of research outputs.
