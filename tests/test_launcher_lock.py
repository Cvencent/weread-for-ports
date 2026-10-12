"""node.sh's single-instance lock, run for real.

node.sh guards the whole launcher with /tmp/weread.lockdir. If a second
instance could take the lock while the first is alive, both would start
gptokeyb and Chromium, and the same physical press would be translated twice --
the "A sometimes works, sometimes does not" symptom the lock exists to prevent.

The functions are lifted verbatim out of node.sh and run under bash, so the
test exercises the shipped logic rather than a paraphrase of it.
"""
import pathlib
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = (ROOT / "launcher/node.sh").read_text(encoding="utf-8").replace("\r\n", "\n")


def bash_path():
    found = shutil.which("bash")
    if found:
        return found
    for candidate in (r"C:\Program Files\Git\bin\bash.exe",
                      r"C:\Program Files\Git\usr\bin\bash.exe"):
        if pathlib.Path(candidate).exists():
            return candidate
    return None


def extract_function(name):
    """Lift a shell function out of node.sh, braces balanced."""
    start = NODE.index("\n%s() {" % name)
    index = NODE.index("{", start)
    depth = 0
    for offset in range(index, len(NODE)):
        if NODE[offset] == "{":
            depth += 1
        elif NODE[offset] == "}":
            depth -= 1
            if depth == 0:
                return NODE[start + 1:offset + 1]
    raise AssertionError("unbalanced " + name)


class SingleInstanceLockTests(unittest.TestCase):
    def setUp(self):
        self.bash = bash_path()
        if not self.bash:
            self.skipTest("bash is not available")
        self.directory = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.lockdir = (self.directory / "lockdir").as_posix()
        self.pidfile = (self.directory / "pid").as_posix()

    def write_script(self, body):
        script = self.directory / "instance.sh"
        script.write_text(
            "#!/bin/bash\nset -u\n"
            "LOCKDIR=%s\nPIDFILE=%s\n%s\n%s\n"
            % (self.lockdir, self.pidfile, extract_function("acquire_lock"), body),
            encoding="utf-8", newline="\n")
        return script

    def run_script(self, script, timeout=90):
        proc = subprocess.run([self.bash, str(script)], capture_output=True,
                              timeout=timeout)
        # The messages are Chinese; decode explicitly rather than letting the
        # platform codec fail the run.
        return (proc.stdout.decode("utf-8", "replace"),
                proc.stderr.decode("utf-8", "replace"), proc.returncode)

    def held_pid(self):
        path = self.directory / "lockdir" / "pid"
        return path.read_text(encoding="utf-8").strip() if path.exists() else None

    def test_a_second_instance_is_refused_while_the_first_is_alive(self):
        script = self.write_script(
            'acquire_lock\necho "HOLDING pid=$$"\nsleep 3\nrm -rf "$LOCKDIR"\necho RELEASED\n')
        first = subprocess.Popen([self.bash, str(script)], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
        try:
            # Wait for the first instance to actually own the lock.
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline and self.held_pid() is None:
                time.sleep(0.05)
            pid = self.held_pid()
            self.assertIsNotNone(pid, "the first instance never took the lock")

            out, _, _ = self.run_script(script)
            self.assertNotIn("HOLDING", out,
                             "a second instance took a lock held by pid %s" % pid)
            self.assertIn(pid, out, "the refusal should name the owning pid")
        finally:
            first.wait(timeout=60)
            first.stdout.close()

    def test_the_lock_is_taken_again_after_the_holder_exits(self):
        script = self.write_script(
            'acquire_lock\necho "TOOK pid=$$"\nsleep 1\nrm -rf "$LOCKDIR"\n')
        first_out, _, _ = self.run_script(script)
        self.assertIn("TOOK", first_out)
        self.assertIsNone(self.held_pid(), "the holder should release on exit")

        # A stale directory left behind by a crash must not wedge the launcher.
        stale = self.directory / "lockdir"
        stale.mkdir(parents=True)
        (stale / "pid").write_text("999999", encoding="utf-8")
        out, _, _ = self.run_script(script)
        self.assertIn("TOOK", out, "a stale lock blocked a fresh start")

    def test_a_lock_directory_without_a_pid_file_is_recovered(self):
        # The holder can be killed between mkdir and the pid write, which is
        # exactly the window that would otherwise lock the device out.
        stale = self.directory / "lockdir"
        stale.mkdir(parents=True)
        script = self.write_script(
            'acquire_lock\necho "TOOK pid=$$"\nrm -rf "$LOCKDIR"\n')
        out, _, code = self.run_script(script)
        self.assertIn("TOOK", out)
        self.assertEqual(code, 0)

    def test_the_lock_is_written_next_to_the_profile_and_removed_on_exit(self):
        # cleanup() must drop the lock, or the next launch refuses to start.
        cleanup = extract_function("cleanup")
        self.assertIn('rm -rf "$LOCKDIR"', cleanup)
        self.assertIn("trap cleanup EXIT INT TERM", NODE)


if __name__ == "__main__":
    unittest.main()
