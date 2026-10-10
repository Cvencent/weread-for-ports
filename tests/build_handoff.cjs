const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const output = path.join(root, 'output', 'weread-for-ports-full.md');
const documents = [
  'README.md',
  'docs/verification-v9.md',
  'docs/legacy/ui-v8-verification.md',
  'docs/architecture.md',
  'docs/project-background.md',
  'docs/project-handoff.md',
];
const parts = ['# WeRead for Ports - full source appendix\n'];
for (const name of documents) {
  parts.push(fs.readFileSync(path.join(root, name), 'utf8'));
}
parts.push('# Current source appendix\n\nOnly `extension/shell.css` is loaded; `extension/legacy/style.css` is kept for reference.\n');
const sources = [
  'extension/manifest.json', 'extension/background-v8.1.js', 'extension/content.js',
  'extension/shell.css', 'ports/Weread.sh', 'ports/install.sh', 'ports/uninstall.sh',
  'ports/update_gamelist.py', 'launcher/node.sh', 'launcher/window_guard.py',
  'launcher/input_bridge.py', 'launcher/weread.gptk', 'launcher/操作说明.txt',
];
for (const name of sources) {
  const source = fs.readFileSync(path.join(root, name), 'utf8');
  const language = { '.js': 'javascript', '.json': 'json', '.css': 'css',
    '.sh': 'bash', '.py': 'python' }[path.extname(name)] || 'text';
  parts.push(`## ${name}\n\n\`\`\`${language}\n${source.trimEnd()}\n\`\`\`\n`);
}
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, parts.join('\n\n---\n\n'), 'utf8');
console.log(`Updated ${output}`);