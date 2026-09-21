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

The Android editor can propose the common `sdpatch` v1 actions from
the current profile: typed presentation/EAGL/GLES compatibility switches,
`presentation.outputFit`, or an input layout. Input manifests can provide exact-revision button-to-touch,
D-pad/stick zones, tilt and virtual-cursor stabilization. They use virtual
iPhone/iPad coordinates and are independently selectable in the same profile
UI. The JSON starting point for maintainers is
`templates/input.sdpatch.json`.

Maintainer JSON submissions also accept the audited layout policy
`presentation.virtualScreen: "host-aspect"`. It is not exposed as a generic
Android editor switch: each game needs camera/culling/HUD/input verification.

A visual mapper, multi-step swipe/pinch macros and safe hiding of a game's own
touch controls are later input-format revisions. Resource payloads use the
separate `.sdmod` installer and are never uploaded through the small-manifest
gateway.

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
