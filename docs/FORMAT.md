# Patch format and engine contract

`formatVersion` versions the manifest contract, not an individual patch.
Backward-incompatible changes require a new schema and parser. Patch updates
use repository history and, once remote packages exist, their own package
version field.

## Typed actions only

An action names a general emulator policy. It must never name a Rust function,
memory address or host command. For example:

```json
{
  "actions": {
    "presentation": {
      "presentFlipX": true
    }
  }
}
```

The engine owns the meaning and validation of `presentFlipX`; the manifest
only selects it for a target. This lets an engine implementation improve
without rewriting every game patch.

## Planned action namespaces

- `eagl`: zero-sized drawable recovery, lifecycle strategy and framebuffer
  preservation;
- `uiview`: transform-aware fullscreen policy and legacy layout canvas;
- `presentation`: rotation, mirroring, aspect fit and true-widescreen policy;
- `input`: gamepad bindings and gestures in virtual-device coordinates;
- `resources`: read-only VFS replacements with source/replacement hashes;
- `diagnostics`: bounded logging counters, never permanent per-call tracing.

New fields must be added to JSON Schema, the Rust data model, conflict
resolution, documentation and tests together.

## Profile precedence

Patch values are recommended defaults. The effective configuration is:

```text
engine safe default < matched patch < explicit per-game profile
```

This guarantees a user can disable a problematic patch without rebuilding the
APK. Conflicting matched patches fail closed and produce a readable log.

Every manifest declares `defaultEnabled`. The game-profile selector has three
states:

- `Automatic`: follow `defaultEnabled` from the installed catalog;
- `Enabled`: opt into the patch, while still enforcing bundle ID, version and
  executable SHA-256 targeting;
- `Disabled`: exclude the patch before resolving any of its actions.

An explicit engine setting can still override the effective value produced by
an enabled patch. Patch selection and low-level diagnostic overrides remain
separate, so either layer can be rolled back independently.

## Resource mods

Large HD textures do not belong in compatibility manifests. A future
`.sdmod` package will contain its own manifest and content-addressed files.
The VFS will serve replacements from an overlay while leaving the IPA intact.
Loose PNG/PVR files come first; UE3/Unity/custom container adapters require a
separate audited implementation and memory-budget metadata.
