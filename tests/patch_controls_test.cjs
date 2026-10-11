const fs = require('node:fs');
const p = 'tests/test_controls_contract.py';
let s = fs.readFileSync(p, 'utf8');
const anchor = '    def test_exit_combo_is_explicit(self):\n';
const added = [
'    def test_launcher_clears_a_stale_input_bridge_before_start(self):',
'        text = (ROOT / "launcher/node.sh").read_text(encoding="utf-8")',
'        self.assertIn(\'pkill -f "$INPUT_BRIDGE" 2>/dev/null\', text)',
'',
].join('\n') + anchor;
if (!s.includes('test_launcher_clears_a_stale_input_bridge_before_start')) s = s.replace(anchor, added);
fs.writeFileSync(p, s);
console.log('added stale bridge contract');
