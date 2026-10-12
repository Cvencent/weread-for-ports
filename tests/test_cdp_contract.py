"""Contracts for the shared CDP client that the shell imports at runtime.

`launcher/input_bridge.py` does `import cdp` and `launcher/node.sh` runs
`cdp.py` to recover a dead page, so the client must exist in the repository,
be installed by ports/install.sh, be deployed by tests/deploy.py, and be
guarded by the launcher self-check.
"""
import ast
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CdpClientContractTests(unittest.TestCase):
    def setUp(self):
        self.cdp = (ROOT / "launcher/cdp.py")
        self.bridge = (ROOT / "launcher/input_bridge.py").read_text(encoding="utf-8")
        self.node = (ROOT / "launcher/node.sh").read_text(encoding="utf-8")
        self.install = (ROOT / "ports/install.sh").read_text(encoding="utf-8")
        self.deploy = (ROOT / "tests/deploy.py").read_text(encoding="utf-8")

    def test_cdp_client_is_part_of_the_repository(self):
        self.assertTrue(self.cdp.is_file(), "launcher/cdp.py is missing from the repository")
        tree = ast.parse(self.cdp.read_text(encoding="utf-8"))
        functions = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertIn("pick_page_target", functions)
        self.assertIn("http_json", functions)
        ws = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.ClassDef) and node.name == "WS")
        methods = {node.name for node in ws.body if isinstance(node, ast.FunctionDef)}
        self.assertLessEqual({"call", "close", "recv", "send"}, methods)

    def test_cdp_client_only_uses_the_standard_library(self):
        # The handheld ships Python without pip.
        tree = ast.parse(self.cdp.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertLessEqual(imported, {
            "base64", "hashlib", "json", "os", "re", "socket", "struct", "sys",
            "time", "urllib",
        })

    def test_input_bridge_finds_cdp_next_to_itself_or_in_the_browser_dir(self):
        self.assertIn("import cdp", self.bridge)
        self.assertIn('"/storage/roms/ports/browser"', self.bridge)
        self.assertIn('os.path.dirname(os.path.abspath(__file__))', self.bridge)

    def test_install_and_deploy_ship_the_cdp_client(self):
        self.assertIn("cdp.py", self.install)
        self.assertIn('"launcher/cdp.py":', self.deploy)

    def test_launcher_checks_for_the_cdp_client_before_starting(self):
        self.assertIn('[ -f "$CDP_TOOL" ]', self.node)
        self.assertIn('python3 "$CDP_TOOL" --url', self.node)

    def test_deploy_tolerates_a_device_without_the_cdp_client_yet(self):
        # deploy.py backs up the installed files first. An older install has no
        # cdp.py on disk, so a missing backup must not abort the deployment.
        self.assertRegex(self.deploy, r'optional = \{[^}]*"cdp[.]py"')


if __name__ == "__main__":
    unittest.main()
