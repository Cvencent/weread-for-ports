"""The refactored openPanel() must decide exactly like the original loop.

openPanel() runs on every focus sweep, so it is written to take a single
layout read per candidate. These tests extract both the shipped
implementation and a literal copy of the original loop and compare the
decisions over the cases that can occur on the handheld.
"""
import json
import pathlib
import shutil
import subprocess
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
NODE = pathlib.Path(__file__).resolve().parent / "_openpanel_equivalence.js"


def build_harness():
    """Create the Node harness that compares both implementations."""
    source = (ROOT / "extension/content.js").read_text(encoding="utf-8")

    def extract(name):
        start = source.index("function %s(" % name)
        index = source.index("{", start)
        depth = 0
        for offset in range(index, len(source)):
            if source[offset] == "{":
                depth += 1
            elif source[offset] == "}":
                depth -= 1
                if depth == 0:
                    return source[start:offset + 1]
        raise AssertionError("unbalanced " + name)

    body = "\n".join([
        'var NAV = "a", MENU = "b";',
        'var DOC = { elements: () => [] };',
        'function mine(e){ return !!(e.closest && e.closest("#" + NAV + ",#" + MENU + ",#wr-hh-kbd")); }',
        "var rc = (e) => e._rect;",
        "var innerWidth = 640;",
        "function $$(s){ return DOC.elements(s); }",
        extract("shownSized"),
        extract("shown"),
        extract("openPanel"),
        "function openPanelOld(){",
        ' var sels = [".readerCatalog", ".font-panel-content", "[class*=\\"catalog_\\"]",',
        '             "[class*=\\"float_panel\\"]", "[class*=\\"readerSetting\\"]",',
        '             "[class*=\\"readerNote\\"]", "[class*=\\"menu_container\\"]"];',
        " for (var i = 0; i < sels.length; i++) {",
        "   var l = $$(sels[i]);",
        "   for (var j = 0; j < l.length; j++) {",
        "     var r = rc(l[j]);",
        "     if (shown(l[j]) && r.width > 60 && r.height > 60 &&",
        "         r.left < innerWidth - 20 && r.right > 20 && !mine(l[j])) return l[j];",
        "   }",
        " }",
        " return null;",
        "}",
        "function setDoc(els){ DOC = { elements: () => els }; }",
    ])
    harness = "\n".join([
        "const body = content;",
        "const fn = new Function('document', 'getComputedStyle',",
        "  body + '\\nreturn { openPanel: openPanel, openPanelOld: openPanelOld, setDoc: setDoc };');",
        "const gcs = (e) => e.style || { display: 'block', visibility: 'visible', opacity: '1' };",
        "const impl = fn({}, gcs);",
        "function el(rect, style, ours, connected) {",
        "  return { _rect: rect, isConnected: connected !== false,",
        "    style: Object.assign({ display: 'block', visibility: 'visible', opacity: '1' }, style || {}),",
        "    closest: ours ? () => ({}) : () => null };",
        "}",
        "const cases = [",
        "  ['normal visible panel', el({width:200,height:300,left:10,right:210,top:0,bottom:300})],",
        "  ['too narrow', el({width:50,height:300,left:10,right:60,top:0,bottom:300})],",
        "  ['too short', el({width:200,height:50,left:10,right:210,top:0,bottom:50})],",
        "  ['offscreen right', el({width:200,height:300,left:630,right:830,top:0,bottom:300})],",
        "  ['offscreen left', el({width:200,height:300,left:-190,right:10,top:0,bottom:300})],",
        "  ['display:none', el({width:200,height:300,left:10,right:210,top:0,bottom:300},{display:'none'})],",
        "  ['visibility:hidden', el({width:200,height:300,left:10,right:210,top:0,bottom:300},{visibility:'hidden'})],",
        "  ['opacity 0', el({width:200,height:300,left:10,right:210,top:0,bottom:300},{opacity:'0'})],",
        "  ['opacity 0.02', el({width:200,height:300,left:10,right:210,top:0,bottom:300},{opacity:'0.02'})],",
        "  ['our own dialog', el({width:200,height:300,left:10,right:210,top:0,bottom:300},null,true)],",
        "  ['disconnected', el({width:200,height:300,left:10,right:210,top:0,bottom:300},null,false,false)],",
        "  ['exactly 60 wide', el({width:60,height:300,left:10,right:70,top:0,bottom:300})],",
        "  ['exactly 60 tall', el({width:200,height:60,left:10,right:210,top:0,bottom:60})],",
        "  ['exactly 60x60', el({width:60,height:60,left:10,right:70,top:0,bottom:60})],",
        "  ['one over 60', el({width:61,height:61,left:10,right:71,top:0,bottom:61})],",
        "  ['left edge exactly innerWidth-20', el({width:200,height:300,left:620,right:820,top:0,bottom:300})],",
        "  ['right edge exactly 20', el({width:200,height:300,left:-180,right:20,top:0,bottom:300})],",
        "  ['right edge one past 20', el({width:200,height:300,left:-179,right:21,top:0,bottom:300})],",
        "];",
        "let ok = true;",
        "const out = [];",
        "for (const [desc, e] of cases) {",
        "  impl.setDoc([e]);",
        "  const a = impl.openPanelOld() === e;",
        "  const b = impl.openPanel() === e;",
        "  if (a !== b) ok = false;",
        "  out.push((a === b ? 'ok ' : 'BAD') + ' ' + desc);",
        "}",
        "console.log(out.join('\\n'));",
        "console.log(ok ? 'EQUIVALENCE: PASS' : 'EQUIVALENCE: FAIL');",
        "process.exit(ok ? 0 : 1);",
    ])
    NODE.write_text(harness, encoding="utf-8")
    return body


class OpenPanelEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_harness()

    def test_open_panel_behaves_like_the_original_loop(self):
        body = build_harness()
        harness_source = NODE.read_text(encoding="utf-8")
        # The harness evaluates the shipped implementation alongside a literal
        # copy of the pre-optimisation loop and compares every decision.
        harness_source = harness_source.replace("const body = content;", "const body = %s;" % json.dumps(body))
        NODE.write_text(harness_source, encoding="utf-8")
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not available")
        result = subprocess.run([node, str(NODE)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("EQUIVALENCE: PASS", result.stdout)
        self.assertNotIn("BAD", result.stdout)
        NODE.unlink()

    def test_open_panel_takes_one_layout_read_per_candidate(self):
        source = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        block = re.search(r"function openPanel\(\) \{(.*?)\n  \}", source, re.S).group(1)
        # A single rect read, reused by the visibility check.
        self.assertEqual(block.count("rc(el)"), 1)
        self.assertIn("shownSized(el, r)", block)
        # The cheap checks must run before the style read, and a detached
        # element must never be reported as an open panel.
        self.assertIn("if (!el.isConnected || mine(el)) continue;", block)
        self.assertIn("function shownSized(e, r)", source)


if __name__ == "__main__":
    unittest.main()