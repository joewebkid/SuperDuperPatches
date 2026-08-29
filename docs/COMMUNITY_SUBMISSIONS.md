# Community patch submissions

## User flow

1. Open a running game's menu and choose **Patches**.
2. Review published patches and their `Automatic`, `Enabled`, or `Disabled`
   policy for the current profile.
3. Choose **Propose a community patch** in the game profile.
4. The app builds an `sdpatch` manifest targeted to the imported IPA's exact
   bundle ID, version, and executable SHA-256.
5. Android sends the proposal to the public submission gateway. No GitHub
   account or repository credential is required in the app.
6. The gateway validates and rate-limits the request, then creates a labelled
   GitHub issue using its server-side, narrowly scoped credential.
7. GitHub Actions parses the marked JSON block as untrusted data, validates
   the schema and semantic rules, commits only the manifest plus `index.json`,
   and opens a draft pull request.
8. Maintainers review the evidence, test rollback and isolation, and either
   request changes or merge the patch.

Pressing **Submit patch** is the explicit authorization boundary. The APK
contains no repository token; GitHub credentials remain encrypted on the
gateway host. If the gateway is unavailable, the app can still open the old
manual GitHub form as an explicit fallback.

## What is supported in v1

The first Android editor intentionally exposes only the typed
`presentation.presentFlipX` action. It proves the complete contribution path
without accepting scripts, native code, network requests, or arbitrary file
writes. Widescreen, gamepad/touch layouts, engine compatibility switches, and
resource overlays require separately versioned schema actions with their own
validation and conflict rules.

## Local drafts and published patches

A user-selected profile value is immediately testable but is not automatically
trusted as a distributable patch. A generated submission starts as
`experimental` and `defaultEnabled: false`. Published catalog entries become
selectable after they are reviewed, merged, and bundled with a subsequent app
build. Remote signed catalog updates are a separate future feature.

## Security boundary

- Exact bundle ID, bundle version, and executable SHA-256 are mandatory.
- Community submissions cannot use legacy weak matching.
- Unknown manifest properties and action kinds are rejected.
- A patch never mutates the original IPA.
- Each launch resolves patch state from a clean base profile.
- User issue text is never executed as shell code.
