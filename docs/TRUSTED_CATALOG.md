# Signed patch catalog plan

Remote patch discovery must not become a remote-code or downgrade channel.
Automatic downloads remain disabled until this TUF-style path is implemented.

## Roles

- **root**: offline threshold keys and role delegation. The APK ships trusted
  root metadata and accepts only monotonic root-version updates.
- **targets**: package path, length, SHA-256, schema version, bundle ID and risk
  metadata. Mach-O overlays use a separately delegated, higher-threshold role.
- **snapshot**: exact versions and hashes of all delegated metadata, preventing
  an inconsistent catalog view.
- **timestamp**: short-lived pointer to the latest snapshot, detecting freeze
  and rollback attacks.

Manifest hashes verify the exact IPA preimage and reconstructed file;
repository signatures authenticate who published the package. Both are needed.

## Client behavior

1. Update trusted root metadata before any other role.
2. Reject expired, rollbacked, incorrectly signed or oversized metadata.
3. Resolve one consistent snapshot and download a target to a temporary file.
4. Verify target length and SHA-256 before opening the ZIP.
5. Run JSON Schema, semantic, path, budget, payload and game-target checks.
6. Publish atomically; retain the last-known-good metadata on any failure.

No GitHub token or signing key belongs in the APK. Community submission remains
an untrusted-data workflow; maintainers review and sign accepted state outside
the app.

## Not implemented yet

The current code packages schemas, validates local archives, verifies exact
preimages/results and records package hashes in the working-cache manifest. It
does not yet fetch a remote catalog, sign metadata, rotate keys or enable an
unsigned package automatically. Those features must land together with expiry,
rollback and last-known-good tests.
