"""netguard() must add a route through the router that actually exists.

node.sh repairs a missing default route before starting Chrome, because the
USB networking hook can drop the wifi default route and leave the browser on
chrome-error://chromewebdata.

The original built the gateway by string surgery on the wlan0 address, so it
always produced x.y.z.1. On a network whose router is not .1 the route it
installs points nowhere, which is the exact failure netguard exists to
prevent. It now prefers a gateway the kernel already knows about and only
guesses when there is nothing to read.

netguard() is extracted from node.sh and run against a stub `ip` that
reproduces real `ip route` / `ip -4 addr` output, so this exercises the shipped
shell function rather than a copy of it.
"""
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
def bash_path():
    """Where bash actually lives, so this runs on Windows and Linux."""
    found = shutil.which("bash")
    if found:
        return found
    for candidate in (r"C:\Program Files\Git\bin\bash.exe",
                      r"C:\Program Files\Git\usr\bin\bash.exe"):
        if pathlib.Path(candidate).exists():
            return candidate
    return None
NODE_SH = ROOT / "launcher" / "node.sh"

HARNESS = r"""
%s

ROUTES=""
ADDR=""
case "$1" in
  present) ROUTES='default via 192.168.7.1 dev wlan0 proto dhcp metric 600'
           ADDR='    inet 192.168.7.42/24 brd 192.168.7.255 scope global wlan0' ;;
  guess1)  ROUTES='192.168.7.0/24 dev wlan0 proto kernel scope link src 192.168.7.42'
           ADDR='    inet 192.168.7.42/24 brd 192.168.7.255 scope global wlan0' ;;
  guess2)  ROUTES='10.0.0.0/24 dev wlan0 proto kernel scope link src 10.0.0.5'
           ADDR='    inet 10.0.0.5/24 brd 10.0.0.255 scope global wlan0' ;;
  cross)   ROUTES='default via 192.168.7.254 dev eth0 metric 50'
           ADDR='    inet 192.168.7.42/24 brd 192.168.7.255 scope global wlan0' ;;
  bare)    ROUTES=""
           ADDR='    inet 192.168.7.42/24 brd 192.168.7.255 scope global wlan0' ;;
esac

ADDED=""
ip() {
  case "$1" in
    route)
      case "${2:-}" in
        show)
          if [ "${3:-}" = "default" ]; then
            case "$ROUTES" in default*) printf '%%s\n' "$ROUTES" ;; *) : ;; esac
          else
            printf '%%s\n' "$ROUTES"
          fi ;;
        add)
          shift 2
          while [ $# -gt 0 ]; do
            [ "$1" = "via" ] && { ADDED="$2"; break; }
            shift
          done ;;
        "") printf '%%s\n' "$ROUTES" ;;
      esac ;;
    -4|addr) printf '%%s\n' "$ADDR" ;;
  esac
}

netguard
if [ -n "$ADDED" ]; then printf 'GATEWAY=%%s\n' "$ADDED"; else printf 'GATEWAY=\n'; fi
"""


def netguard_source():
    source = NODE_SH.read_text(encoding="utf-8")
    match = re.search(r"^netguard\(\) \{.*?^\}\n", source, re.S | re.M)
    if not match:
        raise AssertionError("netguard() was not found in launcher/node.sh")
    return match.group(0)


class NetguardTests(unittest.TestCase):
    def setUp(self):
        self.bash = bash_path()
        if not self.bash:
            self.skipTest("bash is not available")

    def run_case(self, case):
        script = HARNESS % netguard_source()
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False,
                                         encoding="utf-8") as handle:
            handle.write(script)
            path = handle.name
        result = subprocess.run([self.bash, path, case], capture_output=True,
                                text=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for line in result.stdout.splitlines():
            if line.startswith("GATEWAY="):
                return line[len("GATEWAY="):].strip()
        self.fail("netguard produced no GATEWAY line: %r" % result.stdout)

    def test_an_existing_default_route_is_left_alone(self):
        self.assertEqual(self.run_case("present"), "",
                         "a working route must not be replaced")

    def test_it_uses_the_gateway_the_kernel_knows(self):
        # Only a default route on another interface is available, but it names
        # the real router. The old code would have guessed 192.168.7.1.
        self.assertEqual(self.run_case("cross"), "192.168.7.254")

    def test_it_falls_back_to_the_address_guess(self):
        self.assertEqual(self.run_case("guess1"), "192.168.7.1")
        self.assertEqual(self.run_case("guess2"), "10.0.0.1")
        self.assertEqual(self.run_case("bare"), "192.168.7.1")


if __name__ == "__main__":
    unittest.main()
