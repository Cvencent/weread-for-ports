"""Static checks over the extension sources.

These are the defects a linter finds but the unit tests never reach, because
each one sits in a code path the functional tests do not execute.

The motivating find: scheduleRefresh() was declared as a nested function inside
boot(), and sameDocumentNavigate() -- which lives at module scope -- called it.
Every in-page navigation raised a ReferenceError that the surrounding
try/catch swallowed, so settleLoading() and syncRetry() never ran and the
shell stayed stale until a full page load.
"""
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
CONTENT = (ROOT / "extension/content.js")
WORKER = (ROOT / "extension/background-v8.1.js")
ESLINT_CONFIG = ROOT / "tools/eslint.config.mjs"


def function_body(source, name):
    """The text of a top-level `function name() {...}` inside content.js."""
    marker = "  function %s(" % name
    start = source.index(marker)
    lines = source[start:].split("\n")
    for index, line in enumerate(lines):
        if line == "  }":
            return "\n".join(lines[:index + 1])
    raise AssertionError("could not find the end of " + name)


class NestedScopeTests(unittest.TestCase):
    """Functions must not be referenced from a scope that cannot see them."""

    def setUp(self):
        self.source = CONTENT.read_text(encoding="utf-8")

    def test_every_callable_is_defined_outside_boot(self):
        # Anything boot() owns is invisible to the rest of the file.
        boot = function_body(self.source, "boot")
        nested = set(re.findall(r"^\s{4}function (\w+)\(", boot, re.M))
        self.assertTrue(nested, "boot() should still own something local")

        callers = re.findall(r"\b(\w+)\(\)", self.source)
        for name in sorted(nested):
            # Only a problem if something outside boot() calls it.
            outside = self.source.count(name + "(") - boot.count(name + "(")
            self.assertEqual(outside, 0,
                             "%s() is declared inside boot() but called %d time(s) "
                             "from module scope" % (name, outside))

    def test_schedule_refresh_is_reachable_from_module_scope(self):
        self.assertTrue(
            "  var refreshTimer = null;\n  function scheduleRefresh() {" in self.source,
            "scheduleRefresh() is not declared at module scope")
        self.assertTrue(
            "try { syncNav(); scheduleRefresh(); } catch (x) {}" in self.source,
            "the navigation path no longer schedules a shell refresh")
        # boot() must not shadow it.
        self.assertNotIn("function scheduleRefresh()",
                         function_body(self.source, "boot"),
                         "boot() still shadows the module-scope scheduleRefresh")

    def test_the_navigation_refresh_is_not_swallowed_silently(self):
        # The call sits in a try/catch, so a ReferenceError from an
        # out-of-scope helper would never surface. Assert both names resolve.
        block = function_body(self.source, "sameDocumentNavigate")
        calls = [l for l in block.splitlines() if "scheduleRefresh()" in l]
        self.assertEqual(len(calls), 1, calls)
        for name in re.findall(r"\b(\w+)\(\)", calls[0]):
            self.assertIn("function %s(" % name, self.source,
                          "%s() is called but never defined" % name)


class RedeclarationTests(unittest.TestCase):
    def setUp(self):
        self.source = CONTENT.read_text(encoding="utf-8")

    def declarations(self, body):
        return [line.strip() for line in body.splitlines()
                if re.match(r"\s*var (\w+)", line)]

    def test_focus_first_declares_its_binding_once(self):
        body = function_body(self.source, "focusFirst")
        seen = {}
        for line in self.declarations(body):
            name = line.split()[1].rstrip(";=,)")
            seen[name] = seen.get(name, 0) + 1
        # `var` hoists, so a second declaration in the same function scope is
        # the same variable and the first assignment silently wins.
        self.assertEqual(seen.get("remembered"), 1, seen)

    def test_ensure_visible_declares_each_binding_once(self):
        body = function_body(self.source, "ensureVisible")
        seen = {}
        for line in self.declarations(body):
            name = line.split()[1].rstrip(";=,)")
            seen[name] = seen.get(name, 0) + 1
        self.assertEqual(seen.get("r"), 1, seen)


class ForInGuardTests(unittest.TestCase):
    """for..in over data decoded from the network must skip inherited keys."""

    def setUp(self):
        self.source = CONTENT.read_text(encoding="utf-8")

    def test_every_for_in_body_filters_inherited_keys(self):
        loops = list(re.finditer(
            r"for \(var (\w+) in (\w+)\) \{\n(?P<body>(?:.|\n)*?)\n\s*\}", self.source))
        self.assertGreaterEqual(len(loops), 2, "expected the decoded-payload loops")
        for loop in loops:
            name, target = loop.group(1), loop.group(2)
            body = loop.group("body")
            self.assertIn(
                "Object.prototype.hasOwnProperty.call(%s, %s)" % (target, name),
                body,
                "for..in over %s copies inherited keys" % target)


class LintTests(unittest.TestCase):
    """Run the real linter when it is available, so the sweep stays honest."""

    def test_extension_passes_the_linter(self):
        npx = shutil.which("npx")
        if not npx:
            self.skipTest("npx is not available")
        try:
            proc = subprocess.run(
                [npx, "--yes", "eslint", "--config", str(ESLINT_CONFIG),
                 str(CONTENT), str(WORKER)],
                capture_output=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as error:
            self.skipTest("eslint is not usable here: %s" % error)
        output = proc.stdout.decode("utf-8", "replace")
        errors = [l for l in output.splitlines() if " error " in l]
        self.assertEqual(errors, [], output[-4000:])


if __name__ == "__main__":
    unittest.main()
