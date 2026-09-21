import copy
import json
import unittest
from pathlib import Path

from build_controller_catalog import LIBRARY, RECIPES, REVIEWED, ROOT, make_manifest, outputs, reviewed_recipe
from validate_catalog import validate_input_actions


class ControllerCatalogTests(unittest.TestCase):
    def test_reviewed_combat_layouts_are_exact_opt_in_and_keep_stick_roles(self):
        for digest, recipe in json.loads(REVIEWED.read_text(encoding="utf-8")).items():
            game = {"title": "Test", "executableSha256": digest,
                    "bundleId": recipe["bundleId"], "bundleVersion": recipe["bundleVersion"]}
            patch = make_manifest(game, {})
            self.assertFalse(patch["defaultEnabled"])
            self.assertEqual(patch["status"], "experimental")
            self.assertEqual(patch["actions"]["input"], recipe["input"])
            validate_input_actions(ROOT / "templates/input.sdpatch.json", patch["actions"]["input"])
            for key, value in [("bundleId", "wrong.game"), ("bundleVersion", "wrong"),
                               ("executableSha256", "0" * 64)]:
                mismatch = {**game, key: value}
                self.assertIsNone(reviewed_recipe(mismatch))
                self.assertEqual(make_manifest(mismatch, {})["actions"]["input"],
                                 {"cursorMode": "relative", "cursorClickButton": "A"})

    def test_library_has_exact_independently_selectable_coverage(self):
        games = json.loads(LIBRARY.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(games), 48)
        generated = outputs(games)
        for path, content in generated.items():
            self.assertEqual(path.read_text(encoding="utf-8"), content, str(path))
        index = json.loads(generated[ROOT / "index.json"])
        patches = [json.loads((ROOT / entry["path"]).read_text(encoding="utf-8"))
                   for entry in index["patches"] if entry["kind"] == "input"]
        self.assertEqual(len(patches), len(games))
        for game in games:
            found = [p for p in patches if p["target"]["bundleId"] == game["bundleId"]
                     and game["bundleVersion"] in p["target"]["bundleVersions"]
                     and game["executableSha256"] in p["target"]["executableSha256"]]
            self.assertEqual(len(found), 1)
            self.assertFalse(found[0]["target"].get("allowLegacyWeakMatch", False))

    def test_pointer_fallback_never_claims_gameplay_or_changes_rendering(self):
        games = json.loads(LIBRARY.read_text(encoding="utf-8"))
        recipes = json.loads(RECIPES.read_text(encoding="utf-8"))
        for game in games:
            patch = make_manifest(game, recipes)
            self.assertEqual(set(patch["actions"]), {"input"})
            if game["bundleId"] not in recipes and not reviewed_recipe(game):
                self.assertFalse(patch["defaultEnabled"])
                self.assertEqual(patch["status"], "experimental")
                self.assertEqual(patch["actions"]["input"], {
                    "cursorMode": "relative", "cursorClickButton": "A"})

    def test_cursor_contract_rejects_reserved_buttons_and_double_touches(self):
        path = ROOT / "templates/input.sdpatch.json"
        valid = {"cursorMode": "relative", "cursorClickButton": "A"}
        validate_input_actions(path, valid)
        for addition in [
            {"cursorMode": "script"}, {"cursorClickButton": "Back"},
            {"buttons": [{"button": "A", "x": 10, "y": 20}]},
            {"landscapeLayout": {"buttons": [{"button": "A", "x": 10, "y": 20}]}},
            {"arbitraryCode": "not allowed"},
        ]:
            with self.assertRaises(ValueError):
                validate_input_actions(path, {**valid, **addition})

    def test_orientation_layouts_keep_role_conflict_checks(self):
        path = ROOT / "templates/input.sdpatch.json"
        layout = {"cursorStick": "right", "portraitLayout": {
            "leftStickToTouch": {"x": 10, "y": 20, "width": 80, "height": 80}}}
        validate_input_actions(path, layout)
        invalid = copy.deepcopy(layout)
        invalid["cursorStick"] = "left"
        with self.assertRaises(ValueError):
            validate_input_actions(path, invalid)

    def test_legacy_mappings_are_no_longer_hidden_in_default_options(self):
        recipes = json.loads(RECIPES.read_text(encoding="utf-8"))
        for file in (ROOT.parent / "superduper_default_options.txt",
                     ROOT.parent / "android/app/src/main/assets/superduper_default_options.txt"):
            for line in file.read_text(encoding="utf-8").splitlines():
                if line.partition(":")[0] in recipes:
                    self.assertNotIn("-to-touch=", line)
                    self.assertNotIn("-tilt-offset=", line)


if __name__ == "__main__":
    unittest.main()
