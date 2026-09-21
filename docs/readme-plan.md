# README design and verification plan

This plan treats the README as a tested public interface rather than a marketing page.

## Concepts retained from MOZAK and Genome

1. **Lead with the contract:** state what the tool does, what it does not do, and who owns decisions.
2. **Show a runnable path early:** keep the first example limited to behavior that exists in the current release.
3. **Separate explanation layers:** README for orientation, focused documents for architecture and security, command help for exact syntax.
4. **Make trust boundaries visible:** label untrusted inputs, proposal-only outputs, approval gates, and unsupported capabilities.
5. **Pair claims with verification:** publish status, tests, receipts, and acceptance criteria rather than implying maturity.

## External skill incorporated

The public `trkbt10/indexion-skills@indexion-readme` skill was selected from the skills.sh search because it had the strongest usage signal in the results and was already available locally. Its useful concepts are:

- assemble documentation from explicit sources of truth
- do not overwrite existing package documentation implicitly
- verify README edits for accidental deletion or unrelated drift
- keep generated API material separate from hand-written Overview, Usage, Options, and Examples

Monokl does not adopt Indexion as a runtime dependency. The workflow concepts are retained in a tool-neutral form.

## Public README acceptance checks

- Every quickstart command succeeds from a clean editable installation.
- The status statement matches implemented CLI routes.
- Security claims match `docs/security.md`.
- Planned features are clearly labeled and never presented as available.
- Links resolve and repository-local paths use portable relative links.
- A secret scan and tracked-file review pass before every public release.
- README changes are diff-reviewed for removed sections and unrelated rewrites.

## Planned maintenance workflow

1. Update the authoritative implementation or focused document first.
2. Update only the README sections affected by that change.
3. Run the quickstart and test suite from a clean environment.
4. Review the README diff for removed promises, changed boundaries, and stale status.
5. Publish only after the repository safety and release checks pass.
