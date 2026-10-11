"""The Nuxt flat-payload decoder must not leak devalue type tags as data.

__NUXT_DATA__ uses devalue's flat format: the array holds every value once and
references between them are indexes. A plain array is encoded as a list of
numeric indexes, so element 0 of an untagged array is always a number and a
leading string can only be a type tag.

decodeNuxtFlat branched on the tags it knew (Reactive, Ref, Set, Map, ...) and
otherwise decoded the whole array from index 0, which pushed an unrecognised
tag name into the result as a phantom first element and shifted every real
value by one. Suggestions are read straight out of this payload, so a Nuxt
upgrade that added a tag would have shifted the whole recommendation batch.
"""
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = pathlib.Path(__file__).resolve().parent / "_nuxt_decode.js"


class NuxtDecodeTests(unittest.TestCase):
    def run_harness(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        return subprocess.run([node, str(HARNESS)], capture_output=True, text=True)

    def test_unknown_tags_never_become_data(self):
        result = self.run_harness()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DECODE: PASS", result.stdout)
        self.assertNotIn("BAD", result.stdout)

    def test_decoder_skips_the_tag_for_tagged_arrays(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        body = re.search(r"function decodeNuxtFlat\(text\) \{(.*?)\n    return \{ value",
                          source, re.S).group(1)
        self.assertIn("typeof kind === 'string' ? 1 : 0", body)
        # The old unconditional loop is gone.
        self.assertNotIn("for (var i = 0; i < item.length; i++) list.push", body)

    def test_every_known_tag_is_still_unwrapped(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        body = re.search(r"function decodeNuxtFlat\(text\) \{(.*?)\n    return \{ value",
                          source, re.S).group(1)
        for tag in ("ShallowReactive", "Reactive", "Ref", "EmptyRef", "Set", "Map"):
            self.assertIn(tag, body, tag)


if __name__ == "__main__":
    unittest.main()