# Ordered overlay package format

An `.sdmod` is a separately installed ZIP-compatible package. It is not an
IPA, never contains a complete original executable, and is never bundled into
the Super Duper APK. The archive contains `manifest.sdmod.json` plus
content-addressed payloads under `payload/`.

The runtime follows one invariant:

```text
clean IPA + enabled ordered overlays + profile -> disposable working bundle
                                      saves -> separate writable sandbox
```

The original IPA is never rewritten. Every rebuild starts in a new staging
directory, extracts the exact IPA, applies the resolved overlay stack, verifies
every result and then atomically publishes the working cache. An error removes
the entire staging directory. `Documents`, `Library` and save-state archives
are outside both the package store and working bundle, so enabling, removing or
reordering a mod cannot replace a save.

## Versions

- v1 (`schema/sdmod-v1.schema.json`) remains supported for full resource-file
  replacements. It cannot modify Mach-O files.
- v2 (`schema/sdmod-v2.schema.json`) is the canonical ordered-overlay format.
  It requires the exact IPA SHA-256 as well as bundle version and executable
  SHA-256, and supports `replace` plus `vcdiff` operations.

Both schemas use JSON Schema 2020-12. CI runs `check-jsonschema` against every
template and the standalone validator performs the same semantic and archive
checks used by Android. The schemas are also packaged in the APK for editors
and diagnostics; Android's strict parser remains the final local trust boundary.

## Ordered overlay rules

Each manifest has a deterministic `priority`, `dependsOn` and
`conflictsWith`. The resolver sorts independent packages by priority then ID,
but always applies dependencies first. A cycle, missing dependency or conflict
aborts before the working cache is published.

Two enabled packages may target the same `guestPath` only when the later one
depends on the earlier one. Its `sourceSha256` must then equal the earlier
operation's `resultSha256`. This makes the overlay chain explicit instead of
silently applying two patches to an unknown intermediate file.

Every v2 operation declares a safe bundle-relative `guestPath`; hashes for the
source, content-addressed payload and result; exact payload/result sizes; and
bounded output/resident-memory budgets. `Info.plist` is excluded because it
needs a typed semantic action. Absolute roots, `..`, backslashes, duplicates,
undeclared ZIP members, symlinks and encrypted members are rejected.

## VCDIFF/xdelta profile

Binary changes use RFC 3284 VCDIFF with the manifest profile
`rfc3284-xdelta3-no-extensions`. Android rejects xdelta application headers,
Adler32 window extensions and secondary compression. Source, delta and result
are independently SHA-256 verified, and decode is bounded to 256 MiB per file.
A full Mach-O payload is forbidden; `targetClass: "macho"` is accepted only
with `type: "vcdiff"`, and the decoded result must still be Mach-O.

Create a compatible payload with xdelta3 3.x installed:

```text
python scripts/make_vcdiff.py clean-file modified-file payload/change.vcdiff
```

This invokes the equivalent of:

```text
xdelta3 -S -A -n -a -e -s clean-file modified-file change.vcdiff
```

Those switches disable secondary compression, application metadata, Adler32
and the newer armor application header. The helper prints the exact hashes and
sizes to copy into the manifest.

## Build and validation

Place payload files at their declared paths next to the manifest, then run:

```text
python scripts/build_sdmod.py manifest.sdmod.json output.sdmod --engine-version 0.2.3
python scripts/validate_sdmod.py output.sdmod --engine-version 0.2.3
```

The builder refuses to overwrite an output, writes stable ZIP metadata and
ordering, validates the result, and prints its SHA-256. The complete archive
hash belongs in repository target metadata because a package cannot contain
its own digest.

## Trust and distribution

Local fail-closed validation does not make a download trusted. Until signed
repository metadata is implemented, remote automatic installation stays
disabled and packages require explicit import. `TRUSTED_CATALOG.md` defines
the later TUF roles, rollback protection and last-known-good behavior.

Packages may include only payloads the author may redistribute. Binary deltas
can still contain copyrighted fragments and require the same licence evidence
and review as complete resource replacements.
