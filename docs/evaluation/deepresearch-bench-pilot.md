# DeepResearch-Bench pilot protocol

This protocol pre-registers one calibration run before Monokl attempts a nine-task pilot. The calibration validates generation, official evaluation, provenance, cost accounting, and artifact packaging. It is not a leaderboard result and it is not a reproduction of HyperResearch's undisclosed nine-task pilot.

## Pinned benchmark

- Repository: [Ayanami0730/deep_research_bench](https://github.com/Ayanami0730/deep_research_bench)
- Commit: `852f4022d1f98fb707222e395405136e8f0e8d52`
- Code license: MIT
- Query manifest: `data/prompt_data/query.jsonl`
- Query manifest SHA-256: `62b197a264a027fd4e2e795ff322a82dd6d566f5e350596ccc7572539ec987d1`
- Benchmark size: 100 tasks, split into 50 Chinese and 50 English tasks across 22 fields

The official current evaluator uses GPT-5.5 for RACE, GPT-5.6 Luna for article cleaning, and GPT-5.4 Mini for FACT. It accepts OpenAI or OpenRouter as the LLM backend. FACT additionally requires Jina-backed page retrieval. The historical Gemini evaluator remains on the upstream `Gemini-2.5` branch, but this protocol follows the current evaluator so a later submission can use the maintained leaderboard procedure.

## Pre-registered selection

The calibration task is selected without reading reference reports or existing system scores. `select_calibration.py` filters the pinned manifest to English tasks, hashes `monokl-drb-calibration-v1:<task-id>` with SHA-256, and selects the lexicographically smallest digest.

Reproduce the selection:

```bash
python3 docs/evaluation/select_calibration.py /path/to/deep_research_bench/data/prompt_data/query.jsonl
```

The selected task is **ID 95**, topic **Religion**, selection digest `00588ede469eaaaf62d6f13b86cb9b72798b8152c7458723028b7d73cb4e853c`:

> Create comprehensive, in-depth study notes for the Diamond Sutra (Vajracchedikā Prajñāpāramitā Sūtra). These notes should offer deep analysis and interpretation from various perspectives, exploring its teachings and relevance in contexts such as daily life, the workplace/career, business practices, marriage, parenting, emotional well-being, and interpersonal dynamics.

This is a calibration choice, not a claim that task 95 is representative on its own. The later nine-task pilot needs a separately pre-registered stratification rule.

## Frozen Monokl configuration proposed for approval

- Source revision: the exact Monokl commit at execution time, recorded before the run starts
- Installed CLI: record `monokl --version`
- Profile: `full`, without profile overrides
- Model routing: `{"default":"gpt-5.6-sol"}` so every stage uses one available model and route changes do not confound the first calibration
- Search and fetch providers: record the exact `monokl` configuration and credential-backed services without storing secrets
- Hard budget: `$70` API-equivalent for the Monokl run
- Concurrency: one benchmark task only
- Retry policy: retry only a failed bounded worker when its inputs are unchanged
- Stop conditions: budget block, missing required capability, unrecoverable provider failure, absent required artifact, or failed final verification

The single-model route is deliberately simple. Specialized routing can be evaluated later, after the basic generation and evaluation path is known to work.

## Generation procedure

1. Clone the pinned benchmark commit into disposable scratch space and verify the query manifest hash.
2. Create an isolated Monokl vault and save task 95 as the run query file.
3. Record `monokl jcode doctor --project . --json`, `monokl jcode routes --json`, `monokl profile show full -j`, the Monokl Git commit, installed version, provider configuration, and environment metadata.
4. Set `MONOKL_MODEL_ROUTES_JSON='{"default":"gpt-5.6-sol"}'`.
5. Initialize the real run with `monokl run init <tag> --profile full --budget 70 --query-file <query.md> -j`.
6. Execute all required Monokl stages, preserving actual provider and model provenance in stage artifacts.
7. Require `monokl run verify` and `monokl run finish` to pass before evaluation. A blocked or failed run is published as such and is not silently replaced.
8. Export the final report into the official benchmark JSONL shape: `{"id": 95, "prompt": "...", "article": "..."}`.

No paid generation begins without a separate owner approval of the exact source commit, route map, providers, and `$70` ceiling.

## Official evaluation procedure

Use the pinned upstream evaluator without rewriting its prompts. Place the one-row Monokl JSONL under `data/test_data/raw_data/monokl-calibration.jsonl`. Run the RACE and FACT stages against the pinned query manifest, limiting processing to the selected record by preparing a one-row query manifest derived byte-for-byte from task 95.

Required evaluator configuration:

```text
LLM_BACKEND=openrouter or openai
RACE_MODEL=openai/gpt-5.5 or gpt-5.5
CLEAN_MODEL=openai/gpt-5.6-luna or gpt-5.6-luna
FACT_MODEL=openai/gpt-5.4-mini or gpt-5.4-mini
JINA_API_KEY=<provided outside artifacts>
```

Evaluation credentials are never committed. Before evaluation, record the provider, exact model identifiers, evaluator commit, non-secret configuration, and planned evaluator ceiling. The evaluator cost remains unmeasured until one official run succeeds, so it requires separate approval together with generation.

## Required artifacts

Store the public calibration package under `docs/evaluation/runs/drb-task-95/`:

- `protocol.json`: every frozen identity, model, provider, budget, and timestamp needed for reproduction
- `question.json`: task ID, topic, prompt, selection seed, selection digest, manifest hash, and benchmark commit
- `monokl-route.json`: resolved stage routes and actual model provenance
- `run-receipt.json`: run state, profile, spend, wall time, worker count, source count, failures, retries, and final verification
- `article.jsonl`: official one-row benchmark submission
- `race/`: raw RACE outputs and `race_result.txt`
- `fact/`: extraction, deduplication, scrape, validation, and `fact_result.txt`
- `artifact-manifest.json`: relative paths, byte sizes, and SHA-256 hashes
- `README.md`: result, limitations, reproduction commands, and explicit non-leaderboard wording

The private vault may retain additional working artifacts. Public output must not contain credentials, cookies, private browser state, or unrelated source content.

## Reporting boundary

The allowed claim after a successful calibration is: Monokl completed one pre-registered DeepResearch-Bench task and the pinned official evaluator produced the recorded RACE and FACT outputs at the recorded cost and runtime.

Do not claim benchmark superiority, representativeness, reproduction of HPR's 57.77, or leaderboard standing from one task. Failed or blocked execution remains evidence about operability and cost, not research quality.

## Next approval packet

Before execution, present the owner with:

1. Exact Monokl source commit and installed version.
2. Task 95 and its deterministic selection receipt.
3. `{"default":"gpt-5.6-sol"}` as the proposed generation route.
4. Official evaluator commit `852f4022d1f98fb707222e395405136e8f0e8d52` and its three evaluator models.
5. A `$70` generation ceiling, a separate evaluator ceiling based on provider pricing, and the proposed output root.
