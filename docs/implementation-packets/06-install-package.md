# Packet 06: Build installation and packaging

## Goal
Install the HPR-derived CLI and Monokl Jcode extension through one safe, repeatable workflow.

## Required outputs
- Python wheel and source distribution.
- Jcode skill payload with version manifest and hashes.
- Non-interactive installer and guarded uninstaller.
- Local installation receipt recording exact versions and paths.
- Third-party license inventory and upstream attribution.

## Installation behavior
- Detect the Jcode home and supported skill locations explicitly.
- Install create-only or upgrade only files owned by a verified prior receipt.
- Refuse symlink, traversal, drifted managed-file, and partial-install hazards.
- Roll back staging on failure.
- Keep research vaults and user data outside package-owned directories.

## Acceptance checks
1. Install succeeds in an isolated HOME and Jcode discovers `/monokl`.
2. Reinstall is idempotent or performs a verified upgrade.
3. User-modified managed files are not silently overwritten.
4. Uninstall removes only receipt-owned bytes.
5. Wheel metadata, command entry points, skills, assets, and licenses are complete.

## Stop conditions
Block release if installation requires manual copying, writes outside declared roots, or cannot recover cleanly from interruption.
