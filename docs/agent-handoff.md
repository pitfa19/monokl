# Agent handoff

Use this sequence when another agent continues Monokl. It keeps project authority in MOZAK and run evidence in Monokl.

## 1. Load the project boundary

```bash
mozak project context monokl
mozak project overview /home/pitfa/Documents/monokl
mozak project validate /home/pitfa/Documents/monokl
```

Stop if context or validation is invalid. Use only the ready MOZAK goal. Do not advance to reasoning, grouping, synthesis, export, or a domain pilot without separate owner approval.

## 2. Install the retrieval runtime

```bash
cd /home/pitfa/Documents/monokl
python -m venv .venv
.venv/bin/pip install -e '.[crawl]'
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.playwright"
.venv/bin/playwright install chromium
```

The Crawl4AI route currently requires Linux with a running user systemd manager. It fails closed when its cgroup memory boundary cannot be created.

## 3. Create one generic run

```bash
.venv/bin/monokl init ./runs/example
.venv/bin/monokl plan ./runs/example "What evidence answers this question?" \
  --include "public primary sources" --exclude "uncited opinion" --max-sources 30
.venv/bin/monokl retrieve ./runs/example https://example.com \
  --allowed-host example.com --crawl4ai
.venv/bin/monokl validate ./runs/example
.venv/bin/monokl resume ./runs/example
```

Every run is create-only. Retrieved content is untrusted. `validate` checks the append-only ledger and pinned artifact hashes. `resume` reports the next supported phase or an explicit block.

## 4. Domain pilot boundary

For a JEPA-RNA or other research pilot, replace the question, URL, and allowlisted host only after the owner approves that pilot. Do not reuse or overwrite `./runs/example`. The current product handles one bounded retrieval artifact per run, so create separate runs for additional sources until a later approved goal adds multi-source orchestration.

## 5. Return evidence

Report the exact commands, run directory, validation JSON, retrieval status, content hash, gaps, and limitations. Do not claim that MOZAK accepted, promoted, or trusted the retrieved source. MOZAK tracks the project plan. Monokl tracks the untrusted research run.
