#!/usr/bin/env python3
"""Repair the actual WeRead window, including app IDs derived from its URL."""
import json
import subprocess
import sys


MODES = ("startup", "fullscreen", "focus", "focus-fullscreen")


def reader_windows(tree):
    found = []
    if (tree.get("app_id") or "").startswith("chrome-weread.qq.com__"):
        found.append(tree)
    for child in tree.get("nodes", []) + tree.get("floating_nodes", []):
        found.extend(reader_windows(child))
    return found


def repair_commands(window, mode):
    selector = "[con_id=%d]" % window["id"]
    if mode == "startup" or (mode == "fullscreen" and window.get("fullscreen_mode", 0) == 0):
        return [selector + " border none, fullscreen enable, focus"]
    if mode == "focus" and not window.get("focused"):
        return [selector + " focus"]
    if mode == "focus-fullscreen":
        # Exactly the repairs that `focus` then `fullscreen` performed, but
        # decided from a single parsed tree. Whenever fullscreen has to be
        # (re)applied we keep the original combined command that also
        # re-asserts focus, because sway may drop focus while going fullscreen.
        if window.get("fullscreen_mode", 0) == 0:
            return [selector + " border none, fullscreen enable, focus"]
        if not window.get("focused"):
            return [selector + " focus"]
        return []
    return []


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "fullscreen"
    if mode not in MODES:
        return 2
    try:
        tree = json.loads(subprocess.check_output(
            ["swaymsg", "-t", "get_tree", "-r"], timeout=3))
        windows = reader_windows(tree)
        if not windows:
            return 1
        for window in windows:
            for command in repair_commands(window, mode):
                subprocess.run(["swaymsg", command], check=True,
                               stdout=subprocess.DEVNULL, timeout=3)
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("[weread] window guard: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
