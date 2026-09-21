# PDF backend decision

Date: 2026-09-22
Baseline commit: `df300e77535f73f151af9b2e6d8021bf6dd4fea7` (`df300e7`, `Import pinned HyperResearch 0.11.1 core`)
Packet: `docs/implementation-packets/03-pdf-backend.md`

## Decision

Retain PyMuPDF as the PDF backend for the imported HyperResearch code for now.

No permissively licensed candidate demonstrated parity against the required HyperResearch behavior in Packet 03. PyMuPDF is therefore retained for technical compatibility, not because its license is equivalent to the rest of the project.

## Release disclosure

PyMuPDF is not MIT-licensed. PyMuPDF is offered under AGPL-3.0 or a commercial license from Artifex.

Implications for downstream users:

- If a downstream build, distribution, or network service includes PyMuPDF under the AGPL path, the downstream user is responsible for complying with AGPL-3.0 obligations.
- If AGPL-3.0 obligations are not acceptable for a downstream product or service, the downstream user should obtain an appropriate commercial PyMuPDF license or remove/replace the PDF lane.
- This repository's own code license does not relicense PyMuPDF, MuPDF, or any other third-party component.
- This note is a documentation disclosure, not legal advice.

## Required capabilities from Packet 03

The backend has to support these imported HyperResearch behaviors:

| Requirement | Evidence in imported source | Why it matters |
| --- | --- | --- |
| Extract ordered text from ordinary scholarly PDFs | `src/hyperresearch/web/pdf.py:141-223` opens a PDF from bytes and calls `page.get_text("text")` for each page. | The fetch pipeline stores extracted paper text as research notes. |
| Handle common scholarly PDF layouts adequately | `src/hyperresearch/core/agent_docs.py` tells agents that PDF URLs are extracted directly through PyMuPDF. | HPR expects PDFs to be first-class sources, including papers reached through arXiv and OA resolvers. |
| Preserve page-level locators or at least page boundaries | `src/hyperresearch/web/pdf.py:183-206` extracts page by page and joins pages with page separators, and stores page count metadata at `:220`. | Citation, provenance, and review workflows need page-aware extraction boundaries even though the current note body does not yet persist explicit page numbers per paragraph. |
| Fail explicitly on unsupported PDFs | `src/hyperresearch/web/pdf.py:156-203` reports missing PyMuPDF, non-PDF bytes, tiny downloads, open failures, page-read failures, and image-only documents. | The CLI can disclose why a PDF lane declined rather than silently producing junk text. |
| Respect fetch safety and resource bounds | `src/hyperresearch/web/pdf.py:100-131` routes downloads through `safe_get` with timeout, byte cap, TLS verification, and private-host controls from `FetchSettings`. | PDF support must not bypass the SSRF and resource controls used by the web fetchers. |

## Candidate comparison

| Candidate | License posture | Observed parity status | Decision |
| --- | --- | --- | --- |
| PyMuPDF | AGPL-3.0 or commercial license. | Already wired into imported source and covered by existing PDF lane behavior. It opens from bytes, reports failures, extracts page text, preserves page iteration, and stores raw PDF bytes. | Retain with explicit AGPL/commercial disclosure. |
| pypdf | BSD-style permissive license. | Not demonstrated to match the imported behavior for page text ordering, scholarly multi-column extraction, damaged/encrypted failure modes, and byte-stream integration. No project test or fixture corpus in this packet proved parity. | Do not switch in Packet 03. |
| pdfminer.six | MIT license. | Not demonstrated to match the imported behavior for reliability, failure reporting, page separator semantics, and integration with the existing PDF lane. No project test or fixture corpus in this packet proved parity. | Do not switch in Packet 03. |
| pypdfium2 | Apache-2.0 for Python bindings, with bundled/native PDFium licensing and notice review required. | Not demonstrated to match the imported behavior. Its permissive posture is more complex than a pure Python MIT/BSD dependency because redistribution may include native PDFium artifacts and notices. | Do not switch in Packet 03. |

## Reproducible evidence references

Local commands used for this decision:

```bash
git rev-parse HEAD
git log --oneline -5
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
for name in sorted(k for k in mods if k not in stdlib and k not in internal and not k.startswith('_')):
    print(name, len(mods[name]))
print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['dependencies'])
print(tomllib.loads(pathlib.Path('pyproject.toml').read_text())['project']['optional-dependencies'])
PY
rg -n "import pymupdf|from pymupdf|fitz" src/hyperresearch
rg -n "pdf|PyMuPDF|pymupdf|PDF_FAILURE" tests src/hyperresearch/web/pdf.py
```

Primary local evidence:

- `pyproject.toml:24-34` lists `pymupdf>=1.24` as a required dependency.
- `src/hyperresearch/web/pdf.py:51-83` imports PyMuPDF and emits a failure reason when missing.
- `src/hyperresearch/web/pdf.py:141-223` implements extraction through PyMuPDF.
- `src/hyperresearch/web/pdf.py:226-299` implements PDF download, error reporting, and fallbacks.
- `tests/test_web_pdf.py` exercises the PDF lane, arXiv URL conversion, raw PDF preservation, SSRF/TLS refusal behavior, image-only/no-text failures, malformed/small/non-PDF failures, and provider fallback behavior.
- `docs/third-party-license-inventory.md` records the dependency/license inventory used by this decision.

External license references to verify at release time:

- PyMuPDF project license documentation: <https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright>
- PyMuPDF PyPI project metadata: <https://pypi.org/project/PyMuPDF/>
- Artifex commercial licensing page: <https://artifex.com/licensing/>
- pypdf project metadata: <https://pypi.org/project/pypdf/>
- pdfminer.six project metadata: <https://pypi.org/project/pdfminer.six/>
- pypdfium2 project metadata: <https://pypi.org/project/pypdfium2/>

## Code licenses versus API/service terms

This decision concerns code dependencies and redistributable package licenses.

It does not evaluate API or website terms for services that HyperResearch may call or help users visit, such as Exa, Tavily, CORE, OpenAlex, Crossref, Unpaywall, Semantic Scholar, Serply, publisher sites, browser-mediated pages, or search providers. Those are service terms of use and account/API-key obligations, not open-source code licenses for the installed Python packages. They still matter operationally, but they are tracked separately from this license inventory.

## Limitations

- This packet did not implement a replacement backend or run a fixture corpus comparing PyMuPDF, pypdf, pdfminer.six, and pypdfium2 on identical PDFs.
- The source currently preserves page iteration and page count, but not a structured per-span page locator model in the note body.
- Imported tests demonstrate current PDF lane behavior, not legal compliance.
- License names in package metadata can be incomplete or stale. Release managers should re-check upstream metadata and bundled license files before publishing binaries or container images.
- This review is documentation-only. It does not change `pyproject.toml`, source code, package extras, or runtime behavior.
