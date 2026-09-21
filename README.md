# Super Duper Patches

Public catalog: https://joewebkid.github.io/SuperDuperPatches/ .
The machine-readable discovery file is `remote-index.json`; each manifest is
published at its `catalog/…` path with an exact SHA-256 and byte length.
Downloading a manifest does not enable it: newly fetched unsigned patches
require an explicit per-game opt-in. Automatic trust and binary overlays still
require the signed-catalog design in `docs/TRUSTED_CATALOG.md`.

This is the source tree for the standalone `SuperDuperPatches` catalog. It
contains declarative compatibility metadata only. The emulator embeds a
built-in subset and can stage separately downloaded exact-revision JSON
manifests. Downloaded new IDs remain off until enabled in a game profile;
signed automatic trust is a later milestone.

## Package classes

| Kind | Purpose | Mutates the original IPA? |
| --- | --- | --- |
| `compatibility` | Selects typed EAGL, UIKit, GL and audio policies | No |
| `presentation-layout` | Aspect, widescreen and HUD layout policies | No |
| `input` | Gamepad-to-touch, swipe, pinch and tilt layouts | No |
| `achievement` | Exact-game achievement set and icon catalog | No |
| `resource-mod` | Backward-compatible `.sdmod` v1 resource replacement | No |
| `overlay-mod` | Ordered `.sdmod` v2 replace/VCDIFF overlay | No |
| `binary` | Catalog metadata for a typed binary policy; bytes live only in verified `.sdmod` v2 VCDIFF | No |

Do not publish IPA files, decrypted executables, save data, extracted game
assets, album art or other copyrighted payloads here. A resource mod may link
to a separately hosted package only when its author has the right to
redistribute every included file.

## Layout

```text
catalog/<bundle-id>/<patch-id>.sdpatch.json
schema/sdpatch-v1.schema.json
schema/sdmod-v1.schema.json
schema/sdmod-v2.schema.json
scripts/validate_catalog.py
scripts/validate_sdmod.py
scripts/build_sdmod.py
scripts/make_vcdiff.py
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
The separate resource package boundary and implemented Android runtime are
documented in [docs/MOD_FORMAT.md](docs/MOD_FORMAT.md).
The deliberately not-yet-enabled signed remote path is documented in
[docs/TRUSTED_CATALOG.md](docs/TRUSTED_CATALOG.md).

## Submission from the Android app

The app generates an exact-revision manifest and sends it to the public patch
gateway. The gateway validates and rate-limits it, then opens a labelled issue
with a server-side credential limited to issue creation. The
`Community patch to draft PR` workflow treats the issue body strictly as data,
validates it again, adds only the manifest plus `index.json`, and opens a draft
pull request. No GitHub token or repository write credential is embedded in
the APK.

Community manifests for every implemented v1 `sdpatch` action can be generated
from the current profile: compatibility, presentation layout and input.
Manifests always start as `experimental` and disabled by default.
The generated PR still requires evidence and maintainer review before merge.
