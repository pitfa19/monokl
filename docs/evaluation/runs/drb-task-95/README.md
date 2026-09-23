# DeepResearch-Bench task 95: MONOKL calibration result

This directory contains the completed, **unevaluated** MONOKL result for the pre-registered DeepResearch-Bench calibration task 95.

## Status

- MONOKL full profile: completed all 16 stages
- Binding `monokl run finish drb-task-95`: passed
- Final report: `result.md`
- Official RACE and FACT evaluation: intentionally deferred
- Benchmark claim: none yet. This is a single-question operational calibration result.

## Run summary

- Query: comprehensive Diamond Sutra study notes
- Final length: 4,853 words
- Sources fetched: 70
- Durable notes recorded: 77
- Agent workers recorded: 49
- Generation route: GPT profile requested as `gpt-5.6-sol`
- Measured API-equivalent spend: unavailable, recorded as `0.0` rather than estimated

## Integrity checks passed

Required headings, citation density, quote integrity, retracted-citation screening, scaffold-leak screening, critic artifacts, patch log, polish log, and resolved citation-check findings.

## Files

- `result.md`: final report
- `query.md`: canonical task query
- `SHA256SUMS`: result hash
- `artifacts/run-status.json`: completed run state and counters
- `artifacts/prompt-decomposition.json`: frozen response contract
- `artifacts/patch-log.json`: 27 critic findings, all applied
- `artifacts/cite-check-findings.json`: citation-binding findings
- `artifacts/cite-check-patch-log.json`: six citation fixes, all applied
- `artifacts/polish-log.json`: final hygiene changes
- `artifacts/readability-*.json`: final readability recommendations and selective decisions

The later evaluation stage should preserve this package unchanged, run the pinned official evaluator separately, and store judge outputs beside it rather than editing the generation result.
