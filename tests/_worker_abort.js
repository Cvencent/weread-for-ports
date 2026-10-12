// The MV3 worker's response contract: respond() must fire exactly once, inside
// the 4s budget, whatever the local bridge does.
//
// Regression: the worker only ended the request by aborting it and relied on
// the resulting rejection to reach respond(). A fetch that ignores the abort
// signal left the message channel open forever, so content.js never cleared
// readerInputPending and every later reader key press was swallowed.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const workerPath = path.join(__dirname, '..', 'extension', 'background-v8.1.js');
const source = fs.readFileSync(workerPath, 'utf8');

const BUDGET_MS = 4000;
const WRONG_ORIGIN = 'https://evil.example/';
const READER = 'https://weread.qq.com/web/reader/x';

let listener = null;
let cleared = 0;
let created = 0;

// Each mode returns the promise fetch() hands to the worker.
const modes = {
  // Never settles, and ignores the abort signal the way a wedged socket can.
  hang: function (options) {
    return new Promise(function () {});
  },
  // Honours the signal, like the browser does.
  abortable: function (options) {
    return new Promise(function (_resolve, reject) {
      options.signal.addEventListener('abort', function () {
        const err = new Error('This operation was aborted');
        err.name = 'AbortError';
        reject(err);
      });
    });
  },
  ok: function () {
    return Promise.resolve({ ok: true, json: function () { return Promise.resolve({ ok: true }); } });
  },
  notFound: function () {
    return Promise.resolve({ ok: false, status: 404, json: function () { return Promise.resolve({}); } });
  },
  broken: function () {
    return Promise.resolve({ ok: true, json: function () { return Promise.reject(new Error('bad json')); } });
  },
};

let mode = 'ok';

const sandbox = {
  chrome: { runtime: { onMessage: { addListener(fn) { listener = fn; } } } },
  fetch(url, options) {
    created++;
    return modes[mode](options);
  },
  setTimeout,
  clearTimeout(id) { cleared++; return clearTimeout(id); },
  AbortController,
  JSON, Promise, Error, console,
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(source, sandbox, { filename: workerPath });

if (!listener) {
  console.log('BAD worker registered no onMessage listener');
  process.exit(1);
}

// Resolves with every response the worker produced, so a second respond() is
// visible rather than silently dropped by the test.
function send(message, url) {
  const replies = [];
  const kept = listener(message, { url: url || READER }, function (value) {
    replies.push(value);
  });
  return {
    kept: kept === true,
    replies,
    first: function () { return replies.length ? replies[0] : { __never: true }; },
  };
}

function waitForReply(state, limit) {
  return new Promise(function (resolve) {
    const deadline = Date.now() + limit;
    (function tick() {
      if (state.replies.length) return resolve(state.replies[0]);
      if (Date.now() >= deadline) return resolve({ __never: true });
      setTimeout(tick, 25);
    })();
  });
}

const sleep = function (ms) {
  return new Promise(function (resolve) { setTimeout(resolve, ms); });
};

(async () => {
  let ok = true;
  const say = function (good, label, extra) {
    if (!good) ok = false;
    console.log((good ? 'ok  ' : 'BAD '), label, extra === undefined ? '' : extra);
  };

  // 1. A fetch that never settles and ignores abort must still be answered,
  //    on the 4s budget rather than never.
  mode = 'hang';
  let t0 = Date.now();
  let state = send({ type: 'reader-input', action: 'catalog' });
  await sleep(0);
  say(state.kept, 'a real action keeps the message channel open');
  let first = await waitForReply(state, BUDGET_MS + 2000);
  let elapsed = Date.now() - t0;
  say(first.__never !== true, 'a hanging bridge still produces a response',
    JSON.stringify(first) + ' @' + elapsed + 'ms');
  say(first.ok === false, 'the timeout response reports failure', JSON.stringify(first));
  say(typeof first.error === 'string' && first.error.length > 0,
    'the timeout response carries an error string');
  // content.js only retries messages it recognises; a bare abort message would
  // strand the reader on "操作未完成，请重试".
  say(/input service unavailable/i.test(first.error || ''),
    'the timeout message is one content.js retries', JSON.stringify(first.error));
  say(elapsed >= BUDGET_MS - 200 && elapsed < BUDGET_MS + 1500,
    'the budget fires at 4s, not early or never', elapsed + 'ms');

  // 2. Exactly one response, even after the late request would have settled.
  await sleep(300);
  say(state.replies.length === 1, 'respond() is called exactly once',
    'replies=' + state.replies.length);

  // 3. A request that honours the abort signal answers on the same budget,
  //    which is what the browser actually does.
  mode = 'abortable';
  created = 0; cleared = 0;
  t0 = Date.now();
  state = send({ type: 'reader-input', action: 'settings' });
  first = await waitForReply(state, BUDGET_MS + 2000);
  elapsed = Date.now() - t0;
  say(first.ok === false && /input service unavailable/i.test(first.error || ''),
    'an abortable fetch also reports the retryable error', JSON.stringify(first));
  say(elapsed >= BUDGET_MS - 200 && elapsed < BUDGET_MS + 1500,
    'the abortable path answers on the same budget', elapsed + 'ms');
  await sleep(200);
  say(state.replies.length === 1, 'the abortable path responds once',
    'replies=' + state.replies.length);

  // 4. Normal traffic is untouched.
  mode = 'ok';
  cleared = 0;
  state = send({ type: 'reader-input', action: 'activate' });
  first = await waitForReply(state, 1000);
  say(first.ok === true, 'a healthy bridge is forwarded unchanged', JSON.stringify(first));
  say(Date.now() - t0 >= 0 && cleared > 0, 'the deadline timer is cleared on success',
    'cleared=' + cleared);
  say(state.replies.length === 1, 'the success path responds once',
    'replies=' + state.replies.length);

  // 5. Failure shapes keep their old meaning.
  mode = 'notFound';
  state = send({ type: 'reader-input', action: 'close' });
  first = await waitForReply(state, 1000);
  say(first.ok === false && first.error === 'Input service unavailable',
    'a non-2xx bridge reply is still reported as unavailable', JSON.stringify(first));

  mode = 'broken';
  state = send({ type: 'reader-input', action: 'font-next' });
  first = await waitForReply(state, 1000);
  say(first.ok === false && first.error === 'bad json',
    'a body parse failure still reports its own error', JSON.stringify(first));

  // 6. Messages the worker declines must still be declined synchronously and
  //    must never create a request.
  const beforeDeclined = created;
  const declined = send({ type: 'reader-input', action: 'catalog' }, WRONG_ORIGIN);
  say(declined.kept === false && declined.replies.length === 0,
    'a foreign sender is declined without a request');
  const unknown = send({ type: 'reader-input', action: 'rm -rf' });
  say(unknown.kept === false && unknown.replies.length === 0,
    'a non-input action is declined without a request');
  await sleep(50);
  say(created === beforeDeclined, 'declined messages reach no fetch', 'fetches=' + created);

  console.log('ABORT:', ok ? 'PASS' : 'FAIL');
  process.exit(ok ? 0 : 1);
})();