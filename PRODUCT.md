# Product direction

Monokl is disciplined deep research for Jcode users.

It is not a generic AI research SaaS, a benchmark leaderboard, or a vague "future of knowledge work" story. It is an open-source Jcode integration around a pinned HyperResearch engine with explicit provenance, staged work, critique gates, citation auditing, and persistent research artifacts.

## Audience

### Primary: Jcode researchers

People using Jcode to run serious multi-step research who need structure beyond a single chat thread. They care about:

- preserving evidence across long investigations;
- seeing where claims came from;
- separating drafting from criticism;
- resuming work without losing the method;
- avoiding fake certainty.

### Secondary: Jcode developers and maintainers

People inspecting, packaging, testing, or extending Monokl. They care about:

- clear host-integration boundaries;
- safe skill installation and uninstall receipts;
- route and stage provenance;
- upstream attribution;
- reviewable deltas instead of mystery rewrites.

## Core proposition

Monokl gives Jcode a research method with memory, roles, and audit trails.

The value is not that it magically knows more than a researcher. The value is that it keeps the process disciplined: each stage has a job, reviewers are separate from producers, evidence persists, and the final report has been attacked, patched, cite-checked, and polished.

## Product personality

- **Disciplined.** Every claim should feel placed deliberately, with boundaries and provenance.
- **Investigative.** The voice should invite source work, disagreement mapping, and patient inspection.
- **Pixel-crafted.** Visuals can be warm and distinctive, but they should feel handmade and exact, not glossy or generic.
- **Truthful.** Never imply unsupported benchmarks, full automation, or upstream reinvention.
- **Accessible.** Use skimmable hierarchy, plain verbs, meaningful alt text, and short paragraphs.

## Brand register

Use language like:

- research cockpit;
- staged research;
- evidence discipline;
- critique gates;
- citation audit;
- persistent vault;
- Jcode-native orchestration;
- inherited HyperResearch engine;
- reviewable delta;
- fail-closed safety.

Avoid language like:

- revolutionary;
- autonomous researcher;
- human replacement;
- next-gen AI platform;
- benchmark-winning;
- enterprise-grade without evidence;
- magical, effortless, or fully automatic;
- vague "unlock insights" SaaS phrasing.

## Truth boundaries

Monokl can claim:

- it is a Jcode-focused fork of HyperResearch;
- it preserves the upstream engine and methodology unless a delta doc says otherwise;
- it ships a `monokl` CLI with `hpr` and `hyperresearch` aliases;
- it installs one global Jcode skill and eighteen project-local stage skills;
- it supports Python 3.11 through 3.13;
- it validates model route-map shape while Jcode resolves model availability;
- model routing changes provenance only;
- it uses MIT licensing for the package and records third-party license boundaries.

Monokl should not claim:

- measured superiority over human researchers;
- benchmark results not present in this repository;
- a new retrieval, vault, or citation engine invented by the fork;
- provider independence beyond route configurability;
- complete safety from bad sources;
- that web content can authorize actions.

## Default message hierarchy

1. Open with what Monokl lets a Jcode user do.
2. Name the upstream relationship plainly.
3. Show the quick start.
4. Explain the method in grouped phases.
5. Explain persistence, routing, and safety.
6. Point to docs, attribution, and licenses.

## Accessibility rules

- Prefer short sections with one job each.
- Use descriptive link text.
- Give every meaningful image alt text that says what the image communicates.
- Do not use decorative image alt text as a keyword dump.
- Keep commands copyable and split long setup chains into separate lines.
