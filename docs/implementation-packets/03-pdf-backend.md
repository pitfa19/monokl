# Packet 03: Decide the PDF backend

## Goal
Use the best technically suitable PDF backend while preferring a permissive license.

## Candidates
Evaluate at minimum PyMuPDF and viable permissive alternatives such as pypdf, pdfminer.six, and pypdfium2 when their transitive licensing permits distribution.

## Required HPR capabilities
- Extract ordered text from ordinary scholarly PDFs.
- Handle multi-column pages adequately for HPR ingestion.
- Preserve page-level locators needed by citation and provenance workflows.
- Fail explicitly on encrypted, malformed, image-only, and unsupported PDFs.
- Operate within acceptable time and memory bounds.

## Decision rule
Replace PyMuPDF only if an alternative:
1. Has a distribution-compatible permissive license.
2. Passes all upstream PDF tests or equivalent compatibility tests.
3. Passes a representative fixture corpus, including multi-column and malformed files.
4. Does not introduce a material extraction-quality, reliability, or maintenance regression.

If none qualifies, retain PyMuPDF and document that downstream users must comply with its AGPL-3.0 terms or obtain a commercial license.

## Deliverables
- `docs/pdf-backend-decision.md` with evidence table.
- Reproducible benchmark fixtures or legal references that may be redistributed.
- Dependency and license inventory update.

## Stop conditions
Do not change the backend from license preference alone. Do not retain PyMuPDF without an explicit release disclosure.
