// Load the MV3 service worker under a stub chrome.runtime and prove that the
// document warm-up message is actually answered.
//
// Regression: the action allowlist used to filter 'wake' out before the
// handler could answer it, so the worker was never made resident and the
// first real reader action paid a cold-start round trip.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const workerPath = path.join(__dirname, '..', 'extension', 'background-v8.1.js');
const source = fs.readFileSync(workerPath, 'utf8');

const ALLOWED_INPUT = ['catalog', 'settings', 'activate', 'close',
  'font-previous', 'font-next', 'annotation'];

let listener = null;
const fetches = [];

const sandbox = {
  chrome: {
    runtime: {
      onMessage: {
        addListener(fn) { listener = fn; },
      },
    },
  },
  fetch(url, options) {
    fetches.push({ url, body: JSON.parse(options.body) });
    return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) });
  },
  setTimeout,
  clearTimeout,
  AbortController,
  JSON,
  Promise,
  Error,
  console,
};
sandbox.globalThis = sandbox;

vm.createContext(sandbox);
vm.runInContext(source, sandbox, { filename: workerPath });

if (!listener) {
  console.log('BAD worker registered no onMessage listener');
  process.exit(1);
}

// Messages the worker declines synchronously resolve with a marker, so a
// declined message is distinguishable from one it answered.
function send(message, url) {
  return new Promise((resolve) => {
    let settled = false;
    const kept = listener(message, { url }, (value) => { settled = true; resolve(value); });
    if (!settled) resolve({ __declined: true, kept: kept === true });
  });
}

(async () => {
  let ok = true;
  const say = (good, label, extra) => {
    if (!good) ok = false;
    console.log((good ? 'ok  ' : 'BAD '), label, extra === undefined ? '' : extra);
  };

  // 1. The warm-up message must be answered synchronously.
  const wake = await send(
    { type: 'reader-input', action: 'wake' },
    'https://weread.qq.com/web/shelf');
  say(wake && wake.ok === true, 'wake is answered', JSON.stringify(wake));

  // 2. Warming must not reach the local input bridge.
  say(fetches.length === 0, 'wake performs no HTTP request', 'fetches=' + fetches.length);

  // 3. A real action must still be forwarded, and only from weread.qq.com.
  await send({ type: 'reader-input', action: 'catalog' }, 'https://weread.qq.com/web/reader/x');
  await new Promise((r) => setImmediate(r));
  say(fetches.length === 1 && fetches[0].body.action === 'catalog',
    'catalog is forwarded', JSON.stringify(fetches));

  const before = fetches.length;
  await send({ type: 'reader-input', action: 'catalog' }, 'https://evil.example/');
  await send({ type: 'reader-input', action: 'catalog' }, undefined);
  await new Promise((r) => setImmediate(r));
  say(fetches.length === before, 'foreign senders are ignored');

  // 4. The allowlist still rejects anything outside the input set.
  const beforeBad = fetches.length;
  for (const action of ['wake-up', 'rm -rf', undefined, null, 42]) {
    await send({ type: 'reader-input', action }, 'https://weread.qq.com/web/shelf');
  }
  await new Promise((r) => setImmediate(r));
  say(fetches.length === beforeBad, 'non-input actions are rejected');
  say(ALLOWED_INPUT.every((a) => a !== 'wake'),
    'wake stays distinct from the real input actions');

  // 5. Unrelated message types are ignored.
  const other = await send({ type: 'other' }, 'https://weread.qq.com/');
  say(other.__declined === true && other.kept === false,
    'unrelated message types are ignored', JSON.stringify(other));
  const wrongSender = await send(
    { type: 'reader-input', action: 'catalog' }, 'https://evil.example/');
  say(wrongSender.__declined === true,
    'foreign sender of a valid action is declined synchronously');

  console.log('WORKER:', ok ? 'PASS' : 'FAIL');
  process.exit(ok ? 0 : 1);
})();
