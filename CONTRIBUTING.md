# Contributing a patch

## Before opening a pull request

1. Reproduce the problem with the base profile and tracing disabled.
2. Record bundle ID, displayed version, `CFBundleVersion`, executable SHA-256,
   device model, Android version and GPU/driver.
3. Decide whether the result belongs in the engine instead:
   - if the same malformed EAGL/UIView state appears in multiple unrelated
     apps, implement and test a general engine rule;
   - if the application intentionally depends on one old device/layout quirk,
     submit a declarative patch.
4. Copy `templates/compatibility.sdpatch.json` for a presentation fix or
   `templates/input.sdpatch.json` for a controller layout, then give it a
   stable lowercase ID. Never reuse an ID for unrelated behaviour.
5. Choose `defaultEnabled` deliberately. New experimental patches should
   normally default to `false` until their rollback has been tested; enabling
   them manually still cannot bypass target identity checks.
6. Add a short Markdown test record next to the manifest. Include launch,
   scene transition, suspend/resume, return-to-library and second-game tests.

## Required evidence

- before/after screenshots without copyrighted files embedded in the repo;
- relevant log excerpts, with private paths and account data removed;
- proof that a different executable hash does not match;
- test of `Disabled`/rollback behaviour;
- confirmation that launching a second game receives none of the first
  game's effective settings.

## Review states

- `experimental`: reproduced once; visible behind an explicit warning;
- `verified`: reproduced on two devices or by two independent testers;
- `deprecated`: retained in history/index but never activated.

## Prohibited actions

- arbitrary scripts or native libraries downloaded at runtime;
- writes to the original IPA;
- replacement of executable code without an exact preimage hash;
- wildcards that match unrelated bundle IDs or versions;
- network requests made by a patch action;
- distribution of proprietary game resources without permission.

Run `python scripts/validate_catalog.py` and JSON Schema validation before
submitting. CI performs the same checks.
