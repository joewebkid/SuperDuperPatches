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

## Action namespaces

- `eagl`: zero-sized drawable recovery, lifecycle strategy and framebuffer
  preservation. Runtime v1 implements `recoverSharedRenderbufferStorage` and
  the exact-target `forceLandscapeRenderbuffer` policy for old games that
  recreate a portrait CAEAGLLayer backing store after landscape autorotation.
  `forceDirectPresent` is a last-resort exact-target policy for a drawable
  proven to contain rendered pixels while being absent from the visible Core
  Animation layer tree. It bypasses composition and may hide UIKit overlays,
  so it requires device evidence and a reversible patch;
- `gles`: reversible driver-compatibility policies around individual draws,
  including an exact-target `forceLandscapeViewport` repair that keeps an old
  portrait `320x480` viewport consistent with a landscape EAGL backing store;
- `uiview`: transform-aware fullscreen policy and legacy layout canvas;
- `presentation`: rotation, mirroring, aspect fit and true-widescreen policy;
- `input`: implemented for gamepad buttons, D-pad/stick touch areas, tilt and
  cursor stabilization in virtual-device coordinates; swipe/pinch sequences
  remain planned;
- `network`: exact-revision offline compatibility sinks. `offlineTcpSink`
  accepts a client connection, consumes writes and returns EOF on reads;
  `offlineUdpSink` consumes datagrams and returns no packets. These actions
  are used only when host network access is disabled, never replace real
  networking and do not emulate server responses;
- `.sdmod resources`: replacements materialized into a disposable derived
  bundle with source/replacement hashes; the original IPA stays immutable;
- `diagnostics`: bounded logging counters, never permanent per-call tracing.

New fields must be added to JSON Schema, the Rust data model, conflict
resolution, documentation and tests together.

Network sinks require bundle ID, bundle version and executable SHA-256 to
match. They are deliberately narrower than URL rewriting: a title can pass a
dead optional telemetry or advertisement connection without receiving made-up
protocol data. If host network access is enabled, the ordinary socket path
always wins.

### Native-aspect virtual display

`presentation.virtualScreen: "host-aspect"` is an optional `presentation-layout`
action. It exposes a custom 1x guest canvas with the host aspect and the
selected profile's portrait short dimension. Resolution is frozen at startup;
an explicit custom screen-size override wins. Host rendering scale remains
independent. It is not a generic shader stretch or an automatic HUD fixer.
Audit exact-revision projection, CPU culling and touch layout before enabling
it. GOF2 1.1.4 is the first experimental consumer, default off. Changing
the canvas invalidates disk-state geometry; ordinary saves stay separate.

Some pre-iPhone-5 games build a fixed `320x480` `EAGLView` from a NIB even
after UIKit has accepted the virtual canvas. Such an exact-revision
`presentation-layout` patch may additionally set
`forceVirtualScreenViewBounds: true`. It is valid only together with
`virtualScreen: "host-aspect"`; it makes the `UIWindow` and direct `EAGLView`
use the orientation-aware virtual canvas. This is not a camera/FOV, culling or
HUD fix: verify those separately before enabling the patch by default.

### Final half-turn correction

`presentation.presentRotate180` is a boolean compatibility action. It rotates
the completed frame around its centre in the splash, Core Animation and direct
EAGL presenters. It also inverts that correction for host touch/mouse/cursor
input, after undoing zoom/offset and before the existing UIKit mapping. Fixed
controller bindings remain in the original virtual canvas. It never changes
UIKit orientation, renderbuffer size, viewport or guest matrices. It composes
with existing mirroring and leaves Android menus/HUD upright.

Default is off unless an exact-version/hash patch enables it. Patch selection
offers Auto/Enabled/Disabled; CLI `--engine-present-rotate-180=off` overrides a
patch. Conflicting actions fail closed. This is a workaround for an observed
whole-frame half-turn, not a general fix for UIKit autorotation.

### Input actions

Input patches store coordinates in the virtual iPhone/iPad canvas, never in
Android display pixels. This keeps a layout stable across render scale,
letterboxing and host resolution:

```json
{
  "actions": {
    "input": {
      "touchRemap": true,
      "buttons": [
        { "button": "A", "x": 420, "y": 280 },
        { "button": "Start", "x": 20, "y": 20 }
      ],
      "leftStickToTouch": { "x": 25, "y": 200, "width": 95, "height": 100 },
      "portraitLayout": {
        "buttons": [{ "button": "A", "x": 240, "y": 420 }],
        "leftStickToTouch": { "x": 25, "y": 330, "width": 95, "height": 100 }
      },
      "landscapeLayout": {
        "buttons": [{ "button": "A", "x": 420, "y": 280 }],
        "leftStickToTouch": { "x": 25, "y": 200, "width": 95, "height": 100 }
      },
      "leftDeadzone": 0.1,
      "rightDeadzone": 0.15,
      "accelerometerMode": "device",
      "tiltStick": "none",
      "cursorStick": "right"
    }
  }
}
```

The engine rejects duplicate button entries, invalid areas and conflicts
between simultaneously matched patches. A stick cannot simultaneously own a
touch area, virtual cursor and accelerometer tilt. `stickToTouch` remains a
legacy alias for `leftStickToTouch`; new manifests should use the explicit
left/right fields. Explicit mappings in the selected game profile win over
catalog values.

`touchRemap` is a narrow compatibility transform for an exact title whose
visible OpenGL canvas is landscape but whose UIKit root view remains 320×480.
It runs after UIKit hit-testing and maps that point to the default 480×320
game canvas. Do not enable it merely to compensate for a final-image rotation:
the patch must include a touch acceptance result on the targeted IPA.

`portraitLayout` and `landscapeLayout` are optional independent overrides.
Each may contain `buttons`, `dpadToTouch`, `leftStickToTouch` and
`rightStickToTouch`. Missing entries fall back individually to the shared
mapping above; they are selected from the virtual iOS orientation, not the
Android window shape or final presentation mode.

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

## Ordered overlay mods

Large HD textures do not belong in compatibility manifests. An installed
`.sdmod` contains its own strict manifest and content-addressed files. Android
verifies target identity, engine range, package/payload hashes, paths, budgets,
licensing, dependencies and conflicts, then applies the selected stack to an
atomically published disposable bundle. Changing the engine, IPA or mod stack
invalidates that cache automatically. v1 supports complete resource
replacements. v2 adds exact-IPA `replace` and bounded VCDIFF operations with a
mandatory source/payload/result hash chain. A complete Mach-O payload and all
`Info.plist` replacement remain rejected; Mach-O may only be reconstructed
from an exact preimage through the strict VCDIFF profile.

Validate a distributable archive before publishing it:

```text
python scripts/validate_sdmod.py pack.sdmod --engine-version 0.2.3
```

Loose PNG/PVR/plist/audio resources are the intended v1 payloads. v2 is for
ordered HD-resource and exact binary deltas. Semantic UE3, Unity and custom
container rewrites still require an audited adapter rather than pretending the
archive understands their internal format.
