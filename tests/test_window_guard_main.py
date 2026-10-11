"""window_guard.py main(): check the CLI contract node.sh depends on.

node.sh calls it three ways:
  window_guard.py startup            once, in a 45 s poll loop
  window_guard.py focus              every other tick
  window_guard.py focus-fullscreen   the alternating tick

It treats a non-zero exit as "not ready yet" and loops, so the exit codes have
to distinguish a real repair failure from a mode typo.

swaymsg is replaced in the subprocess namespace rather than on PATH: this
platform will not resolve a shim from PATH, and patching the module keeps the
real get_tree call, the real JSON parsing and the real repair dispatch under
test while replacing only the external binary.
"""
import importlib.util
import io
import json
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_guard():
    spec = importlib.util.spec_from_file_location(
        "window_guard_under_test", ROOT / "launcher" / "window_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


READER = {"app_id": "chrome-weread.qq.com__-Default", "id": 42,
          "focused": True, "fullscreen_mode": 1, "name": "WeRead",
          "nodes": [], "floating_nodes": []}


class StubbedSubprocess:
    """Stands in for the subprocess module inside window_guard."""

    def __init__(self, tree, behaviour="ok"):
        self.tree = tree
        self.behaviour = behaviour
        self.calls = []
        outer = self

        class SubprocessError(Exception):
            pass

        class CalledProcessError(SubprocessError):
            pass

        class TimeoutExpired(SubprocessError):
            pass

        self.SubprocessError = SubprocessError
        self.CalledProcessError = CalledProcessError
        self.TimeoutExpired = TimeoutExpired
        self.DEVNULL = subprocess.DEVNULL

    def check_output(self, argv, timeout=None):
        self.calls.append(list(argv))
        if self.behaviour == "fail":
            raise self.CalledProcessError(1, argv)
        if self.behaviour == "garbage":
            return b"not json at all"
        return json.dumps(self.tree).encode("utf-8")

    def run(self, argv, check=False, stdout=None, timeout=None):
        self.calls.append(list(argv))
        if self.behaviour == "fail":
            raise self.CalledProcessError(1, argv)

        class Completed:
            returncode = 0
        return Completed()


class WindowGuardMainTests(unittest.TestCase):
    def run_guard(self, argv, tree=None, behaviour="ok"):
        module = load_guard()
        stub = StubbedSubprocess(
            tree if tree is not None else READER, behaviour)
        module.subprocess = stub
        saved = sys.argv
        sys.argv = ["window_guard.py"] + argv
        try:
            code = module.main()
        finally:
            sys.argv = saved
        return code, stub.calls

    def test_startup_forces_fullscreen_and_focus(self):
        code, calls = self.run_guard(["startup"])
        self.assertEqual(code, 0)
        self.assertEqual(calls[-1],
                         ["swaymsg", "[con_id=42] border none, fullscreen enable, focus"])

    def test_focus_fullscreen_is_a_no_op_when_nothing_is_wrong(self):
        # node.sh runs this on every other tick, so a needless repair here is a
        # constant stream of swaymsg calls.
        code, calls = self.run_guard(["focus-fullscreen"])
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1, "only the get_tree call should happen")

    def test_focus_fullscreen_repairs_only_what_is_wrong(self):
        unfocused = dict(READER, focused=False)
        code, calls = self.run_guard(["focus-fullscreen"], tree=unfocused)
        self.assertEqual(code, 0)
        self.assertEqual(calls[-1], ["swaymsg", "[con_id=42] focus"])

        notfull = dict(READER, fullscreen_mode=0)
        code, calls = self.run_guard(["focus-fullscreen"], tree=notfull)
        self.assertEqual(code, 0)
        self.assertEqual(calls[-1],
                         ["swaymsg", "[con_id=42] border none, fullscreen enable, focus"])

    def test_an_unknown_mode_is_rejected_without_touching_sway(self):
        code, calls = self.run_guard(["bogus"])
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])

    def test_the_default_mode_is_fullscreen(self):
        code, _calls = self.run_guard([])
        self.assertEqual(code, 0)

    def test_no_reader_window_means_not_ready(self):
        tree = {"id": 1, "app_id": "root", "nodes": [], "floating_nodes": []}
        code, calls = self.run_guard(["focus"], tree=tree)
        self.assertEqual(code, 1, "a missing window must not look like success")
        self.assertEqual(len(calls), 1)

    def test_a_reader_window_under_floating_nodes_is_found(self):
        tree = {"id": 1, "app_id": "root", "nodes": [],
                "floating_nodes": [dict(READER, focused=False)]}
        code, calls = self.run_guard(["focus-fullscreen"], tree=tree)
        self.assertEqual(code, 0)
        self.assertEqual(calls[-1], ["swaymsg", "[con_id=42] focus"])

    def test_swaymsg_failures_are_reported_not_swallowed(self):
        code, _calls = self.run_guard(["startup"], behaviour="fail")
        self.assertEqual(code, 1)

    def test_unparseable_sway_output_is_reported(self):
        code, _calls = self.run_guard(["focus"], behaviour="garbage")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
