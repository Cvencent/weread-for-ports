"""Run the suite the way CI does: without the optional test dependencies.

playwright is only needed for the browser tests, paramiko only for talking to a
real handheld. Neither is installed on a plain CI runner, so the suite has to
skip those tests rather than fail to import them. This hides both modules and
reports whether the run is clean - the check that would have caught the first
tagged release failing its own test step.

    python tools/simulate_ci_tests.py
"""
import builtins
import io
import os
import pathlib
import unittest


BLOCKED = ("playwright", "paramiko")
_real_import = builtins.__import__


def _import(name, *args, **kwargs):
    if name.split(".")[0] in BLOCKED:
        raise ImportError("No module named %r (simulated CI)" % name.split(".")[0])
    return _real_import(name, *args, **kwargs)


def main():
    builtins.__import__ = _import
    root = pathlib.Path(__file__).resolve().parents[1]
    # Run from the repo root with the tests directory relative, which is how
    # the README invokes the suite and the only form discover() accepts.
    os.chdir(root)
    suite = unittest.TestLoader().discover("tests", pattern="test_*.py")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    print(stream.getvalue().strip().splitlines()[-1])
    for case, trace in result.errors + result.failures:
        print("PROBLEM:", case.id())
        print(trace.strip().splitlines()[-1])
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
