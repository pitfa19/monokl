# Monokl

## Intent

Build a small, local-first, agent-agnostic research runner that recreates the useful lifecycle of HyperResearch while using Crawl4AI only as a bounded retrieval substrate.

## Desired outcomes

- Turn a scoped research question into durable, reviewable run artifacts.
- Retrieve web sources through a narrow, security-hardened Crawl4AI adapter.
- Let any agent or model participate through versioned JSON task and result contracts.
- Require explicit owner review before grouped research advances or becomes a reusable skill.
- Export provenance-complete, proposal-only artifacts that MOZAK can validate.
- Remain substantially smaller and easier to audit than HyperResearch.

## Boundaries

- No dependency on Claude, OpenAI, Jcode, or another agent SDK in the core.
- No autonomous acceptance of sources, claims, Concepts, plans, or generated skills.
- Web content is untrusted data and cannot authorize actions.
- No logged-in browser profiles, credentials, private-network crawling, embeddings, or permanent research vault in the first release.
- Crawl4AI LLM extraction remains disabled. Retrieval and reasoning are separate boundaries.
- Raw full text is temporary by default; durable artifacts retain bounded evidence, locators, metadata, and hashes.

## Assumptions

- Python is the smallest practical integration layer for Crawl4AI.
- Immutable run directories are sufficient before a shared SQLite index is justified.
- A manual JSON packet adapter is the simplest proof of genuine agent independence.
- MOZAK remains the system of record for project registration, accepted knowledge, and cross-project reuse.

## Open questions

- Which normalized Markdown representation stays stable enough across Crawl4AI upgrades?
- Should the first production adapter invoke Crawl4AI in-process or through a subprocess boundary?
- What minimum source locator survives HTML-to-Markdown conversion reliably?
- When does an owner-supplied URL set need search discovery or adaptive crawling?
- Which parts of the HyperResearch open-access recovery flow are worth reintroducing after the first pilots?
