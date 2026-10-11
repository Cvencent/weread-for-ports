"""The discovery cache must store only what same-document navigation uses.

The discovery page is server rendered and can be hundreds of KB. Only the
content-wrapper block and the Nuxt book payload are ever read, so the cache
holds those two slices rather than the whole document. These tests pin the
extraction to the original inline slicing and guard the size limit.
"""
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
HARNESS = pathlib.Path(__file__).resolve().parent / "_discovery_payload_equivalence.js"


class DiscoveryCacheTests(unittest.TestCase):
    def test_extracted_block_matches_the_original_slicing(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        result = subprocess.run([node, str(HARNESS)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EQUIVALENCE: PASS", result.stdout)
        self.assertIn("blocks identical: true", result.stdout)

    def test_cache_stores_slices_not_the_whole_document(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("function discoveryPayload(html)", source)
        self.assertIn("DISCOVERY_CACHE_MAX = 262144", source)
        # The route view is filled from the cached block, not a re-parse.
        self.assertIn("host.innerHTML = payload.block;", source)
        self.assertIn("suggestionBooks = payload.books;", source)
        # The old whole-document cache entry is gone.
        self.assertNotIn("getDiscoveryHtml", source)

    def test_large_payloads_are_not_persisted_to_session_storage(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        block = re.search(r"function getDiscoveryPayload\(force\) \{(.*?)\n  \}", source, re.S).group(1)
        self.assertIn("if (payload.block.length <= DISCOVERY_CACHE_MAX)", block)
        self.assertIn("sessionStorage.removeItem('wr-hh-discovery-cache')", block)


if __name__ == "__main__":
    unittest.main()