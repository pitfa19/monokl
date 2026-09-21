# Packet 08: Release and local installation

## Goal
Publish Monokl v0.2.0 and leave a verified local Jcode installation ready for owner testing.

## Preconditions
- Packets 01 through 07 completed with evidence.
- Repository clean and public tests passing.
- License and attribution review complete.
- PDF backend decision published.
- No unresolved critical or high-severity defects.

## Release steps
- Update concise README, changelog, version, and migration notice.
- State clearly that Monokl is derived from HyperResearch and is a Jcode-only extension.
- Build artifacts from the exact release commit.
- Generate and verify checksums and release manifest.
- Tag `v0.2.0`, push, and publish a non-draft GitHub release.
- Install from the published artifact, not the source checkout.

## Acceptance checks
1. Release tag, commit, wheel, skill payload, manifest, and checksums agree.
2. Fresh installation completes from public assets.
3. `monokl --version` reports `0.2.0`.
4. A fresh Jcode session discovers `/monokl`.
5. A bounded installed Jcode startup check discovers `/monokl` and reports its startup requirements without beginning a research run. The owner will perform the first full run separately.
6. Existing `v0.1.0` and archive refs remain available.

## Stop conditions
Do not publish from a dirty tree, local-only artifact, failed parity run, or unresolved license inventory.
