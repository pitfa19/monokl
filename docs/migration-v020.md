# Migrating to Monokl 0.2.0

Monokl 0.2.0 replaces the experimental standalone implementation with the pinned HyperResearch engine and a Jcode-native orchestration layer.

1. Install the `0.2.0` wheel from the GitHub release.
2. Run `monokl jcode install --project .` in the research project.
3. Run `monokl jcode doctor --project . --json`.
4. Load `/monokl` in Jcode.

The `hpr` and `hyperresearch` commands remain compatibility aliases. Existing research vaults remain user-owned and are not stored in the skill installation. The former implementation is preserved by the `archive/pre-hpr-rewrite` branch and `pre-hpr-rewrite-2026-09-21` tag.

PyMuPDF remains required for PDF extraction. It is distributed under AGPL-3.0 or a commercial license. See `docs/pdf-backend-decision.md` before redistributing or operating the PDF lane in a service.
