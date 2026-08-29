# Super Duper Patches

This is the source tree for the standalone `SuperDuperPatches` catalog. It
contains declarative compatibility metadata only. The emulator
embeds the verified built-in subset at compile time; a later release may fetch
a signed index without allowing downloaded native code to execute.

## Package classes

| Kind | Purpose | Mutates the original IPA? |
| --- | --- | --- |
| `compatibility` | Selects typed EAGL, UIKit, GL and audio policies | No |
| `presentation-layout` | Aspect, widescreen and HUD layout policies | No |
| `input` | Gamepad-to-touch, swipe, pinch and tilt layouts | No |
| `resource-mod` | User-installed texture/audio/resource overlay | No |
| `binary` | Version-specific byte patch, reserved for a later audited format | Never in v1 |

Do not publish IPA files, decrypted executables, save data, extracted game
assets, album art or other copyrighted payloads here. A resource mod may link
to a separately hosted package only when its author has the right to
redistribute every included file.

## Layout

```text
catalog/<bundle-id>/<patch-id>.sdpatch.json
schema/sdpatch-v1.schema.json
scripts/validate_catalog.py
templates/
index.json
```

The canonical format is JSON. JSON Schema makes validation deterministic in
the app, CI and third-party tools. A visual editor can provide a friendlier UI
later without introducing a second source format.

## Target safety

Community patches must specify:

1. exact `bundleId`;
2. one or more tested `bundleVersions`;
3. SHA-256 of the unmodified Mach-O executable;
4. a reproducible test plan and rollback instructions.

`allowLegacyWeakMatch` exists only to migrate existing built-in bundle-ID
branches without regressing current users. CI rejects it for community PRs.

Resolution order is deterministic:

1. built-in/catalog patches sorted by `priority`, then `id`;
2. conflicts are rejected before launch;
3. an explicit per-game profile value overrides a patch default;
4. no patch state survives into the next IPA launch.

Android packages the catalog metadata with the APK. Applicable patches appear
in each game's profile as `Automatic`, `Enabled` or `Disabled`; the choice is
stored per profile and enforced again by the Rust resolver at launch.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the review workflow and
[docs/FORMAT.md](docs/FORMAT.md) for action design rules. The full Android to
draft-PR path is documented in
[docs/COMMUNITY_SUBMISSIONS.md](docs/COMMUNITY_SUBMISSIONS.md).

## Submission from the Android app

The app generates an exact-revision manifest and opens a pre-filled GitHub
submission. After the user confirms it, the `Community patch to draft PR`
workflow treats the issue body strictly as data, validates it, adds only the
manifest plus `index.json`, and opens a draft pull request. No GitHub token or
repository write credential is embedded in the APK.

Community manifests always start as `experimental` and disabled by default.
The generated PR still requires evidence and maintainer review before merge.
