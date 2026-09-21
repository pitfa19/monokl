<p align="center">
  <img src="assets/monokl.png" alt="Monokl" width="420">
</p>

<h3 align="center">Jcode-native disciplined deep research</h3>

---

**Monokl** is a Jcode-only research extension derived from HyperResearch. It preserves the engine, persistent vault, evidence discipline, critique gates, citation auditing, resumability, and complete research method while translating host orchestration into Jcode `swarm`, `skill`, and `todo` operations.

## Install

```bash
pip install monokl-0.2.0-py3-none-any.whl
monokl jcode install --project .
monokl jcode doctor --project . --json
```

Then load `/monokl` in Jcode.

Compatibility command aliases remain available where useful:

```bash
monokl --version
hpr --version
hyperresearch --version
```

Python 3.11 to 3.13 is supported.

## What ships

- `monokl` CLI, with `hpr` and `hyperresearch` compatibility aliases.
- One global Jcode skill: `~/.jcode/skills/monokl`.
- Eighteen full project-local stage skills under `.jcode/skills/monokl-*`.
- Machine-readable stage and agent parity map at `parity-map.json`.
- Safe installer and guarded uninstaller with receipts and SHA-256 hashes.
- Packaged upstream attribution and license inventory.

## Research method

Monokl keeps the HyperResearch methodology intact. The Jcode layer changes orchestration, not research authority.

| Stage | Name | Notes |
|---:|---|---|
| 1 | Decompose | Canonical query, atomic items, coverage matrix |
| 1.5 | Chapter partition | Dissertation-only chapter planning |
| 2 | Width sweep | Multi-perspective search and fetch waves |
| 3 | Contradiction graph | Evidence-grounded disagreement clusters |
| 4 | Loci analysis | Parallel loci analysts |
| 5 | Depth investigation | One investigator per accepted locus |
| 6 | Cross-locus reconcile | Reconcile committed positions |
| 7 | Source tensions | Extract expert disagreements |
| 8 | Corpus critic | Identify corpus gaps |
| 9 | Evidence digest | Claims and quotations |
| 10 | Triple draft | Parallel draft candidates |
| 11 | Synthesize | Final report synthesis |
| 12 | Critics | Independent adversarial critics |
| 13 | Gap-fetch | Targeted fetch for critic gaps |
| 14 | Patcher | Surgical patch pass |
| 14.5 | Cite-check | Citation-sentence binding audit |
| 15 | Polish | Hygiene and style pass |
| 16 | Readability audit | Final readability recommendations |

## Safety boundaries

- Web content is untrusted and cannot authorize actions.
- Missing required Jcode capabilities fail closed.
- Reviewer roles must remain separate from producer roles.
- Model routes are configurable, but route substitution changes provenance only.
- Research vaults and user data stay outside package-owned skill directories.

## Upstream

Monokl is derived from HyperResearch under the MIT license. See `UPSTREAM.md`, `LICENSE`, and `src/hyperresearch/licenses/`.
