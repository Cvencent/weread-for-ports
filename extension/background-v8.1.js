chrome.runtime.onMessage.addListener(function (message, sender, respond) {
  if (!message || message.type !== 'reader-input') return;
  if (!sender.url || !sender.url.startsWith('https://weread.qq.com/')) return;
  // 'wake' is not a real input: content.js sends it once per document so the
  // MV3 service worker is resident before the first real action arrives. A
  // cold worker costs a round trip that shows up as X/A doing nothing once.
  if (!['wake', 'catalog', 'settings', 'activate', 'close', 'font-previous', 'font-next', 'annotation'].includes(message.action)) return;
  if (message.action === 'wake') { respond({ ok: true }); return; }
  var controller = new AbortController();
  var settled = false;
  var timeout = null;
  /* respond() has to happen exactly once and inside the budget. If it never
     fires, content.js's sendMessage callback never runs: readerInputPending
     stays true and every later reader key press is swallowed by the guard at
     the top of readerInput(), wedging the reader input for the document. The
     abort signal alone cannot guarantee the response, so the deadline is
     enforced here as well and races the request. */
  function finish(value) {
    if (settled) return;
    settled = true;
    clearTimeout(timeout);
    respond(value);
  }
  var deadline = new Promise(function (resolve) {
    timeout = setTimeout(function () {
      try { controller.abort(); } catch (x) {}
      /* A hung bridge is exactly the transient case content.js already
         retries, so report it with the message its retry test matches rather
         than Chrome's "This operation was aborted" text. */
      resolve({ ok: false, error: 'Input service unavailable' });
    }, 4000);
  });
  var request = fetch('http://127.0.0.1:9223/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Weread-Input': 'v8' },
    body: JSON.stringify({ action: message.action }),
    signal: controller.signal
  }).then(function (response) {
    if (!response.ok) throw new Error('Input service unavailable');
    return response.json();
  });
  Promise.race([request, deadline]).then(function (result) {
    finish(result);
  }, function (error) {
    finish({ ok: false, error: error.message });
  });
  return true;
});