# N.O.V.A. 1.1.0 — review record

The clean IPA's `Info.plist` reports `com.gameloft.NOVA`,
`CFBundleVersion=1.1.0`. SHA-256 of its unmodified Mach-O matches the manifest.
This only proves target identity; the compatibility matrix still rates this
game partial because gameplay rendering flashes.

Acceptance still needed on ARM64: compare launch, menu and a clean 60-second
gameplay segment with this patch disabled and enabled; record screenshots and
whether the flashes disappear. Then test suspend/resume, return to library and
launch a different game. Rollback: choose Disabled in the game profile and
relaunch; verify the original IPA and other game's settings are unchanged.

Keep experimental and opt-in until these checks are recorded.
