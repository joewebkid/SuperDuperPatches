# Red Alert 1.1.0 — review record

The clean IPA's `Info.plist` reports `com.ea.candcra.row`,
`CFBundleVersion=1.1.0`. SHA-256 of its unmodified Mach-O matches the manifest.
This only proves target identity; it does not prove that audio is fixed.

Acceptance still needed on ARM64: compare launch, menu and gameplay audio with
this patch disabled and enabled; record timestamps, glitches and screenshots.
Then test suspend/resume, return to library and launch a different game.
Rollback: choose Disabled for this patch in the game profile and relaunch;
verify the original IPA and the other game's settings are unchanged.

Keep experimental and opt-in until these checks are recorded.
