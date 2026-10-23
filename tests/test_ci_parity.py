"""The suite must survive a runner that lacks playwright and paramiko.

The first tagged release failed its own test step because those imports sat at
module scope and turned a missing optional dependency into a collection error.
Nothing in the repo caught that, because the suite had only ever run on a
developer box that had both installed. This pins the property directly: every
test module must import cleanly with both modules hidden.
"""
import builtins
import importlib
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
BLOCKED = ("playwright", "paramiko")


class ModuleImportParityTests(unittest.TestCase):
    def test_every_test_module_imports_without_the_optional_dependencies(self):
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name.split(".")[0] in BLOCKED:
                raise ImportError("No module named %r (simulated CI)" % name.split(".")[0])
            return real_import(name, *args, **kwargs)

        modules = sorted(p.stem for p in TESTS.glob("test_*.py"))
        self.assertTrue(modules, "no test modules found")

        builtins.__import__ = fake_import
        saved_path = list(sys.path)
        try:
            sys.path.insert(0, str(TESTS))
            for name in modules:
                with self.subTest(module=name):
                    try:
                        importlib.import_module(name)
                    except unittest.SkipTest:
                        pass
                    except ImportError as err:
                        # A missing *optional* dependency must never surface as
                        # an import error for the test module itself.
                        self.fail("%s needs an optional dependency at import "
                                  "time: %s" % (name, err))
        finally:
            sys.path[:] = saved_path
            builtins.__import__ = real_import


if __name__ == "__main__":
    unittest.main()
