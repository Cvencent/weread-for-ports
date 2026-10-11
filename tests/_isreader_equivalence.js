// isReader() previously tested only the FIRST matching container for
// visibility. If a hidden stale container came first, the visible reader was
// ignored and the shell took the browsing branch. This harness pins the fix.
const fs = require('fs');
const path = require('path');

const contentJs = fs.readFileSync(
  path.join(__dirname, '..', 'extension', 'content.js'), 'utf8');

const start = contentJs.indexOf('function isReader() {');
const end = contentJs.indexOf('function hasNav()');
if (start < 0 || end < 0) { console.log('BAD could not locate isReader'); process.exit(1); }

const $ = (sel) => containers[0] || null;
const $$ = (sel) => containers.slice();
function shown(e) { return !!e && e.isConnected && e.shownOk; }

const containers = [];
// The function reads the global location, so drive it through a shim.
globalThis.location = { pathname: '/' };
const isReader = eval('(' + contentJs.slice(start, end) + ')');
function at(pathname) {
  globalThis.location = { pathname };
  return isReader();
}

function reset(list) { containers.length = 0; containers.push(...list); }
const node = (shownOk) => ({ isConnected: true, shownOk });

let ok = true;
const check = (got, want, label) => {
  const pass = got === want;
  if (!pass) ok = false;
  console.log((pass ? 'ok  ' : 'BAD '), label, 'got=' + got, 'want=' + want);
};

function oldIsReader(pathname) {
  const first = containers[0] || null;
  return /\/web\/reader\//.test(pathname) || (first && shown(first) ? true : false);
}

// No containers at all.
reset([]); check(at('/web/shelf'), oldIsReader('/web/shelf'), 'no containers on shelf');

// Reader route wins regardless.
reset([]); check(at('/web/reader/abc'), true, 'reader route');

// A single visible container.
reset([node(true)]);
check(at('/web/shelf'), oldIsReader('/web/shelf'), 'single visible container');

// A single hidden container.
reset([node(false)]);
check(at('/web/shelf'), oldIsReader('/web/shelf'), 'single hidden container');

// THE REGRESSION: hidden stale container first, visible reader second.
reset([node(false), node(true)]);
check(at('/web/shelf'), true, 'visible reader behind a hidden stale container');

// Reverse order.
reset([node(true), node(false)]);
check(at('/web/shelf'), oldIsReader('/web/shelf'), 'visible reader first');

// All hidden.
reset([node(false), node(false)]);
check(at('/web/shelf'), oldIsReader('/web/shelf'), 'all containers hidden');

console.log('EQUIVALENCE:', ok ? 'PASS' : 'FAIL');
process.exit(ok ? 0 : 1);
