"""Contracts for the window guard that repairs focus and fullscreen."""
import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
GUARD = ROOT / "launcher/window_guard.py"


def load_guard():
    spec = importlib.util.spec_from_file_location("window_guard", GUARD)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WindowGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = load_guard()

    def effects(self, commands):
        state = set()
        for command in commands:
            if "focus" in command:
                state.add("focus")
            if "fullscreen enable" in command:
                state.add("fullscreen")
            if "border none" in command:
                state.add("borderless")
        return state

    def test_combined_mode_matches_running_focus_then_fullscreen(self):
        # The guard used to be invoked twice per cycle. `focus-fullscreen`
        # must reach exactly the same window state from a single parsed tree.
        for focused in (True, False):
            for fullscreen in (0, 1, 2):
                window = {"id": 1, "focused": focused, "fullscreen_mode": fullscreen}
                separate = self.effects(
                    self.guard.repair_commands(window, "focus")
                    + self.guard.repair_commands(window, "fullscreen")
                )
                combined = self.effects(
                    self.guard.repair_commands(window, "focus-fullscreen")
                )
                self.assertEqual(separate, combined,
                                 "focused=%s fullscreen=%s" % (focused, fullscreen))

    def test_startup_mode_still_restores_everything_at_once(self):
        for focused in (True, False):
            for fullscreen in (0, 1):
                window = {"id": 3, "focused": focused, "fullscreen_mode": fullscreen}
                self.assertEqual(
                    self.guard.repair_commands(window, "startup"),
                    ["[con_id=3] border none, fullscreen enable, focus"],
                )

    def test_fullscreen_repair_reasserts_focus(self):
        # sway can drop focus while a window goes fullscreen, so applying
        # fullscreen must re-assert focus in the same command.
        window = {"id": 4, "focused": True, "fullscreen_mode": 0}
        for mode in ("fullscreen", "focus-fullscreen"):
            commands = self.guard.repair_commands(window, mode)
            self.assertEqual(len(commands), 1)
            self.assertIn("focus", commands[0])

    def test_healthy_window_produces_no_sway_commands(self):
        # `startup` is excluded on purpose: it always re-asserts the window
        # geometry because it also repairs a border set by a previous run.
        healthy = {"id": 5, "focused": True, "fullscreen_mode": 1}
        for mode in ("focus", "fullscreen", "focus-fullscreen"):
            self.assertEqual(self.guard.repair_commands(healthy, mode), [],
                             "mode %s must not touch a healthy window" % mode)

    def test_unknown_mode_is_rejected(self):
        self.assertNotIn("bogus", self.guard.MODES)
        self.assertEqual(self.guard.repair_commands({"id": 6}, "bogus"), [])


if __name__ == "__main__":
    unittest.main()