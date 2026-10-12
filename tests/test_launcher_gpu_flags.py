"""node.sh must keep the GPU flags that actually reach the Mali-G52.

This is a static test on purpose. The evidence that these flags put WebGL on
real hardware only exists on the handheld (vulkaninfo, /proc/<gpu>/maps, CDP
Runtime.evaluate), none of which can run in CI. What CI *can* do is stop the
flags from silently regressing:

* ``--use-angle=vulkan`` is the backend that reaches Mali-G52. ``gl``/``gles``
  lose WebGL entirely in a real Wayland window on this device, and
  ``swiftshader`` is software rendering.
* ``Vulkan`` must NOT appear in ``--enable-features``. With it, Chromium tries
  to build a Vulkan surface for the Wayland compositor, which always fails here
  ("'--ozone-platform=wayland' is not compatible with Vulkan" plus "Failed to
  create vulkan surface", 6 occurrences per launch when measured). Dropping it
  leaves page WebGL on the same Mali-G52 driver with the noise gone.
"""
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = (ROOT / "launcher/node.sh").read_text(encoding="utf-8").replace("\r\n", "\n")


def chrome_args():
    """Return (line, text) for every argument line passed to ./chrome."""
    match = re.search(r"^\./chrome \\\n(.*?)^\s*$", NODE, re.S | re.M)
    assert match, "could not find the ./chrome invocation in node.sh"
    lines = match.group(1).splitlines()
    # A comment inside a backslash-continued argument list silently swallows
    # every argument after it: bash treats the rest of the line as a comment,
    # so the command runs as "./chrome --test-type ..." and dies with
    # "--use-gl=angle: command not found". Keep comments out of the list.
    for line in lines:
        stripped = line.lstrip()
        assert not stripped.startswith("#"), (
            "comment inside the ./chrome argument list swallows the following "
            "flags: %r" % line)
    return [line for line in lines if line.strip()]


def chrome_flags():
    """The argument list passed to ./chrome, as a single string.

    Comments are skipped on purpose: the block above the invocation documents
    the backends that were measured and rejected (``gl``, ``gles``,
    ``swiftshader``), and a naive substring scan would trip over its own notes.
    """
    return "\n".join(chrome_args())


class LauncherGpuFlagsTest(unittest.TestCase):
    def test_uses_vulkan_angle_backend(self):
        flags = chrome_flags()
        self.assertIn("--use-gl=angle", flags)
        self.assertIn("--use-angle=vulkan", flags)

    def test_angle_backend_is_not_software(self):
        flags = chrome_flags()
        for backend in ("swiftshader", "--use-angle=gl", "--use-angle=gles"):
            self.assertNotIn(backend, flags)

    def test_enable_features_does_not_enable_vulkan(self):
        flags = chrome_flags()
        found = re.search(r"--enable-features=(\S+)", flags)
        self.assertIsNotNone(found, "expected an --enable-features flag")
        features = [f.strip() for f in found.group(1).split(",")]
        self.assertNotIn("Vulkan", features)
        self.assertIn("UseOzonePlatform", features)

    def test_gpu_rasterization_stays_enabled(self):
        self.assertIn("--enable-gpu-rasterization", chrome_flags())


if __name__ == "__main__":
    unittest.main()
