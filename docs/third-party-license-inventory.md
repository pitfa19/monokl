# Third-party license inventory

Date: 2026-09-22
Baseline commit: `df300e77535f73f151af9b2e6d8021bf6dd4fea7` (`df300e7`)
Scope: documentation-only inventory from `pyproject.toml` plus external imports observed in `src/`, `tests/`, and `assets/`.

This inventory distinguishes code package licenses from API/service terms. Package licenses govern installed redistributable software. API/service terms govern network services or websites contacted by users or by optional providers, and are not replaced by package licenses.

## Method

Reproduce the package/import scope with:

```bash
python - <<'PY'
import ast, pathlib, tomllib
stdlib = set(getattr(__import__('sys'), 'stdlib_module_names', ()))
mods = {}
for root in ['src', 'tests', 'assets']:
    for path in pathlib.Path(root).rglob('*.py'):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mods.setdefault(alias.name.split('.')[0], set()).add(str(path))
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods.setdefault(node.module.split('.')[0], set()).add(str(path))
internal = {'hyperresearch'}
print('external imports:')
for name in sorted(k for k in mods if k not in stdlib and k not in internal and not k.startswith('_')):
    print(name, len(mods[name]))
pyproject = tomllib.loads(pathlib.Path('pyproject.toml').read_text())
print('dependencies:', pyproject['project']['dependencies'])
print('optional:', pyproject['project']['optional-dependencies'])
PY
```

Observed external imports on this baseline: `PIL`, `bs4`, `crawl4ai`, `exa_py`, `httpx`, `jinja2`, `matplotlib`, `mcp`, `numpy`, `patchright`, `playwright`, `pydantic`, `pymupdf`, `pytest`, `rich`, `tavily`, `typer`, `watchdog`, `yaml`.

## Runtime dependencies from `pyproject.toml`

| Package requirement | Imported as | Declared scope | License posture | Notes and evidence |
| --- | --- | --- | --- | --- |
| `typer>=0.9.0` | `typer` | Required runtime | MIT | CLI framework. Listed in `pyproject.toml:24-34`; imported throughout `src/hyperresearch/cli/`. Verify: <https://pypi.org/project/typer/>. |
| `rich>=13.0` | `rich` | Required runtime | MIT | Console rendering. Listed in `pyproject.toml:24-34`; imported by CLI output and status code. Verify: <https://pypi.org/project/rich/>. |
| `pyyaml>=6.0` | `yaml` | Required runtime | MIT | YAML/frontmatter parsing. Listed in `pyproject.toml:24-34`; local metadata also reported `License=MIT` for PyYAML 6.0.3. Verify: <https://pypi.org/project/PyYAML/>. |
| `pydantic>=2.0` | `pydantic` | Required runtime | MIT | Settings/model validation. Listed in `pyproject.toml:24-34`; imported in `src/hyperresearch/core/config.py` and models. Verify: <https://pypi.org/project/pydantic/>. |
| `jinja2>=3.1` | `jinja2` | Required runtime | BSD-3-Clause | Template rendering. Listed in `pyproject.toml:24-34`; imported by rendering/template code. Verify: <https://pypi.org/project/Jinja2/>. |
| `platformdirs>=4.0` | `platformdirs` | Required runtime | MIT | User config/data directory resolution. Listed in `pyproject.toml:24-34`; local metadata reported MIT classifier for platformdirs 4.10.0. Verify: <https://pypi.org/project/platformdirs/>. |
| `Crawl4AI>=0.7.3` | `crawl4ai` | Required runtime and optional extra alias | Apache-2.0 in current project metadata, with transitive browser stack review needed | Browser-backed web provider. Listed in `pyproject.toml:24-34` and `pyproject.toml:36-50`; imported by `src/hyperresearch/web/crawl4ai_provider.py`. Verify package metadata and bundled notices before release: <https://pypi.org/project/Crawl4AI/>. |
| `pymupdf>=1.24` | `pymupdf` | Required runtime | AGPL-3.0 or commercial license | PDF backend. Listed in `pyproject.toml:24-34`; imported in `src/hyperresearch/web/pdf.py:60`. This is the material non-permissive dependency. See `docs/pdf-backend-decision.md`. Verify: <https://pypi.org/project/PyMuPDF/> and <https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright>. |
| `httpx>=0.27` | `httpx` | Required runtime | BSD-3-Clause | HTTP client. Listed in `pyproject.toml:24-34`; imported by safe fetch and provider code. Verify: <https://pypi.org/project/httpx/>. |

## Optional dependencies from `pyproject.toml`

| Extra / requirement | Imported as | Declared scope | License posture | Notes and evidence |
| --- | --- | --- | --- | --- |
| `mcp>=1.6,<2` | `mcp` | `mcp`, `parallel`, `all`, `dev` extras | MIT | MCP server/client integration. Listed in `pyproject.toml:42-46` and `:57`; imported in MCP modules. Verify: <https://pypi.org/project/mcp/>. |
| `exa-py>=2.0.0` | `exa_py` | `exa`, `all`, `dev` extras | MIT in current package metadata | Exa provider SDK. Listed in `pyproject.toml:47` and `:56`; imported by Exa provider code. Verify: <https://pypi.org/project/exa-py/>. |
| `tavily-python>=0.3` | `tavily` | `tavily`, `all` extras | MIT in current package metadata | Tavily provider SDK. Listed in `pyproject.toml:48`; imported by Tavily provider code. Verify: <https://pypi.org/project/tavily-python/>. |
| `watchdog>=4.0` | `watchdog` | `watch`, `all`, `dev` extras | Apache-2.0 | File watcher. Listed in `pyproject.toml:49` and `:59`; imported by watch command. Verify: <https://pypi.org/project/watchdog/>. |
| `pytest>=7.4` | `pytest` | `dev` extra | MIT | Test runner only. Listed in `pyproject.toml:51-60`; imported by tests. Verify: <https://pypi.org/project/pytest/>. |
| `pytest-cov>=4.1` | plugin package | `dev` extra | MIT | Coverage plugin only. Listed in `pyproject.toml:51-60`. Verify: <https://pypi.org/project/pytest-cov/>. |
| `ruff>=0.3` | tool package | `dev` extra | MIT | Lint tool only. Listed in `pyproject.toml:51-60`. Verify: <https://pypi.org/project/ruff/>. |
| `mypy>=1.8` | tool package | `dev` extra | MIT | Type checker only. Listed in `pyproject.toml:51-60`. Verify: <https://pypi.org/project/mypy/>. |
| `types-PyYAML>=6.0.12` | stubs | `dev` extra | Apache-2.0 in typeshed distribution metadata | Type stubs only. Listed in `pyproject.toml:51-60`. Verify: <https://pypi.org/project/types-PyYAML/>. |

## Imported third-party modules not declared directly in `pyproject.toml`

These imports are still part of the observed source inventory because they appear in source, tests, or assets. Some are transitive dependencies of declared packages or dev-only asset tooling rather than declared install requirements.

| Imported module | Likely package | Observed scope | License posture | Notes and evidence |
| --- | --- | --- | --- | --- |
| `bs4` | `beautifulsoup4` | Optional runtime fallback in built-in HTML extraction | MIT | Imported lazily in `src/hyperresearch/web/builtin.py`; not listed directly in `pyproject.toml`. Verify whether supplied transitively by Crawl4AI or should be declared before packaging. Package metadata: <https://pypi.org/project/beautifulsoup4/>. |
| `patchright` | `patchright` | Optional browser install/detection path | Apache-2.0 in current package metadata | Imported lazily in install/setup code when present. Not listed directly in `pyproject.toml`; likely transitive/optional through Crawl4AI's stealth adapter. Verify before redistribution: <https://pypi.org/project/patchright/>. |
| `playwright` | `playwright` | Optional browser install/detection path | Apache-2.0 | Imported lazily in install/setup code as browser fallback. Not listed directly in `pyproject.toml`; likely transitive/optional through Crawl4AI. Verify: <https://pypi.org/project/playwright/>. |
| `PIL` | `Pillow` | Asset generation script only | HPND/Pillow license | Imported by `assets/_generate_banner.py`; not runtime code. Local metadata found Pillow 12.3.0 installed. Verify: <https://pypi.org/project/pillow/>. |
| `matplotlib` | `matplotlib` | Asset generation script only | Matplotlib license, BSD-style | Imported by `assets/_generate_benchmark.py`; not runtime code. Local metadata reported the Matplotlib license text for 3.11.1. Verify: <https://pypi.org/project/matplotlib/>. |
| `numpy` | `numpy` | Asset generation script only | BSD-3-Clause | Imported by `assets/_generate_benchmark.py`; not runtime code. Verify: <https://pypi.org/project/numpy/>. |

## API and service terms are not code licenses

The packages above are code dependencies. The following are examples of service/API terms that are outside this code-license inventory:

- Exa service/API terms when using the Exa provider, separate from the `exa-py` package license.
- Tavily service/API terms when using the Tavily provider, separate from the `tavily-python` package license.
- Browser, publisher, search, and scholarly APIs or websites accessed during research, including CORE, OpenAlex, Crossref, Unpaywall, Semantic Scholar, arXiv, Serply, and publisher domains.
- Playwright-managed browser binaries and Crawl4AI browser behavior may have additional third-party notices beyond the Python package metadata.

## Release risks and follow-ups

1. PyMuPDF is the only required runtime dependency in this inventory with an explicit AGPL-3.0/commercial licensing decision point.
2. `bs4`, `patchright`, and `playwright` are imported but not directly declared in `pyproject.toml`; release packaging should verify whether this is intentional transitive usage.
3. Asset-generation imports are not runtime requirements, but generated assets should be treated separately from the scripts that produced them.
4. Package metadata is not a substitute for bundled license files in wheels, sdists, browser binaries, or container images.
5. No legal conclusion is made here. This file is an engineering inventory for release review.
