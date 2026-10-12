// readerInput() must release its re-entry guard even when sendMessage() never
// calls back.
//
// readerInputPending gates every reader key, so it is cleared only inside the
// sendMessage callback. Chrome has no guarantee that callback runs -- a worker
// torn down mid-flight drops the channel without a reply -- which left the
// reader permanently deaf. The worker now enforces its own 4s deadline; this
// harness covers content.js's independent guard on top of it.
//
// Runs the real readerInput source out of content.js against stub DOM and
// chrome.runtime, so the test fails if the guard is ever removed.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const contentPath = path.join(__dirname, '..', 'extension', 'content.js');
const source = fs.readFileSync(contentPath, 'utf8');

// Slice the real function out of the real file.
const start = source.indexOf('  function readerInput(action) {');
if (start < 0) { console.log('BAD readerInput not found'); process.exit(1); }
const lines = source.slice(start).split('\n');
let end = -1;
for (let i = 1; i < lines.length; i++) {
  if (lines[i] === '  }') { end = i; break; }
}
if (end < 0) { console.log('BAD readerInput end not found'); process.exit(1); }
const fnSource = lines.slice(0, end + 1).join('\n');

// The guard budget, read from the source under test.
const guardMatch = /attemptState\.timer = setTimeout\(function \(\) \{[\s\S]*?\}, (\d+)\);/
  .exec(fnSource);
const guardMs = guardMatch ? Number(guardMatch[1]) : NaN;

// A controllable timer, so the harness can compress the guard's real budget.
const clock = createClock(40);
const calls = { hints: [], diags: [], busyDone: [] };
let sendMode = 'never';        // never | ok | fail | okAfter
let pendingCallback = null;
let sentActions = [];

// Virtual timers: setTimeout(fn, ms) fires after ms/SCALE real milliseconds and
// in scheduling order, which is all this harness depends on.
function createClock(scale) {
  let now = 0;
  let seq = 0;
  const pending = [];
  return {
    setTimeout(fn, ms) {
      const id = ++seq;
      pending.push({ id, at: now + (ms || 0), fn });
      pending.sort((a, b) => a.at - b.at || a.id - b.id);
      const due = pending[0];
      setTimeout(() => {
        const i = pending.findIndex((t) => t.id === id);
        if (i < 0) return;
        pending.splice(i, 1);
        now = due.at;
        fn();
      }, (ms || 0) / scale);
      return id;
    },
    clearTimeout(id) {
      const i = pending.findIndex((t) => t.id === id);
      if (i >= 0) pending.splice(i, 1);
    },
  };
}
clock.scale = 40;

const sandbox = {
  document: {
    body: {
      className: '',
      classList: { add() {}, remove() {} },
      appendChild() {},
    },
  },
  location: { pathname: '/web/reader/x' },
  Date, Math, JSON, Array, Promise, Error, console, RegExp,
  // Virtual clock: the 16s budget is asserted below against the real source,
  // but the behavioural run compresses it so the suite stays fast.
  setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout,
  chrome: {
    runtime: {
      lastError: undefined,
      sendMessage(message, callback) {
        sentActions.push(message.action);
        if (sendMode === 'ok') { setTimeout(() => callback({ ok: true }), 1); return; }
        if (sendMode === 'okAfter') { pendingCallback = callback; return; }
        if (sendMode === 'fail') { setTimeout(() => callback({ ok: false, error: 'nope' }), 10); return; }
        // 'never': the callback is dropped, exactly like a dead worker.
      },
    },
  },
  beginReaderBusy() { sandbox.readerBusyState = { started: Date.now() }; return {}; },
  watchReaderBusy() {},
  // Mirrors the real finishReaderBusy(), which owns the failure hint.
  finishReaderBusy(ok) {
    calls.busyDone.push(ok);
    sandbox.readerBusyState = null;
    if (!ok) sandbox.showHint('操作未完成，请重试');
  },
  openPanel() { return null; },
  invalidateNow() {},
  focusAt() {}, focusAtEl() {},
  diag(o) { calls.diags.push(o); },
  showHint(t) { calls.hints.push(t); },
};
sandbox.globalThis = sandbox;
sandbox.window = sandbox;
vm.createContext(sandbox);
vm.runInContext('var readerInputPending = false, readerBusyState = null, focusEl = null;\n' + fnSource, sandbox,
  { filename: 'content.js#readerInput' });

function readPending() { return vm.runInContext('readerInputPending', sandbox); }
function press(action) {
  vm.runInContext('readerInput(' + JSON.stringify(action) + ')', sandbox);
  return readPending();
}

// Sleep on the virtual clock, letting any timer scheduled in that window fire.
const sleep = (ms) => new Promise((resolve) => clock.setTimeout(resolve, ms));

(async () => {
  let ok = true;
  const say = (good, label, extra) => {
    if (!good) ok = false;
    console.log((good ? 'ok  ' : 'BAD '), label, extra === undefined ? '' : extra);
  };

  say(Number.isFinite(guardMs), 'the guard timer is declared in readerInput',
    'budget=' + guardMs + 'ms');
  // Worst legitimate chain: 3 worker budgets + 450ms + 1200ms backoffs.
  say(guardMs > 3 * 4000 + 450 + 1200,
    'the guard is above the slowest legitimate retry chain', guardMs + 'ms > 13650ms');

  // 1. The lost-callback case: the reader must unlock itself.
  sendMode = 'never';
  sentActions = [];
  say(press('catalog') === true, 'readerInput claims the key while in flight');
  say(readPending() === true, 'the re-entry guard is held during the request');
  vm.runInContext('readerInput("catalog")', sandbox);
  say(sentActions.length === 1, 'a second press is swallowed while busy',
    'sent=' + sentActions.length);
  await sleep(guardMs + 400);
  say(readPending() === false, 'the guard is released after the timeout',
    'pending=' + readPending());
  say(calls.busyDone.length >= 1 && calls.busyDone[calls.busyDone.length - 1] === false,
    'the timeout reports failure', JSON.stringify(calls.busyDone));
  say(calls.hints.length >= 1, 'the user is told to retry', JSON.stringify(calls.hints));

  // 2. The reader must work again immediately afterwards.
  // On success readerInput deliberately leaves the overlay to watchReaderBusy(),
  // which polls the DOM until the site settles; so success means "released and
  // never reported as failed", not "busy flipped true". readerInput also clears
  // the flag 100ms after a successful reply, so wait past that.
  calls.hints.length = 0;
  calls.busyDone.length = 0;
  sentActions = [];
  sendMode = 'ok';
  press('settings');
  await sleep(1000);
  say(readPending() === false, 'a normal action still completes',
    'pending=' + readPending());
  say(calls.hints.length === 0, 'a normal action raises no failure hint',
    JSON.stringify(calls.hints));
  say(calls.busyDone.length === 0,
    'a normal action leaves the overlay to the busy watcher',
    JSON.stringify(calls.busyDone));

  // 3. A late reply arriving after the timeout must not double-report.
  calls.hints.length = 0;
  calls.busyDone.length = 0;
  sendMode = 'okAfter';
  press('activate');
  await sleep(guardMs + 400);
  const hintsAfterTimeout = calls.hints.length;
  const doneAfterTimeout = calls.busyDone.length;
  if (pendingCallback) pendingCallback({ ok: true });
  await sleep(200);
  say(readPending() === false, 'a late reply leaves the reader unlocked');
  say(calls.hints.length === hintsAfterTimeout,
    'a late reply adds no second hint',
    hintsAfterTimeout + '->' + calls.hints.length);
  say(calls.busyDone.length === doneAfterTimeout,
    'a late reply finishes the busy state only once',
    doneAfterTimeout + '->' + calls.busyDone.length);

  // 4. An ordinary failure still reports exactly once.
  calls.hints.length = 0;
  calls.busyDone.length = 0;
  sendMode = 'fail';
  press('close');
  await sleep(guardMs + 600);
  say(calls.hints.length === 1, 'a rejected action reports once, not on the timer too',
    'hints=' + calls.hints.length);
  say(readPending() === false, 'a rejected action releases the guard');
  say(calls.busyDone.length === 1, 'a rejected action finishes busy once',
    JSON.stringify(calls.busyDone));

  console.log('GUARD:', ok ? 'PASS' : 'FAIL');
  process.exit(ok ? 0 : 1);
})();