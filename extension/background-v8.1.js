chrome.runtime.onMessage.addListener(function (message, sender, respond) {
  if (!message || message.type !== 'reader-input') return;
  if (!sender.url || !sender.url.startsWith('https://weread.qq.com/')) return;
  // 'wake' is not a real input: content.js sends it once per document so the
  // MV3 service worker is resident before the first real action arrives. A
  // cold worker costs a round trip that shows up as X/A doing nothing once.
  if (!['wake', 'catalog', 'settings', 'activate', 'close', 'font-previous', 'font-next', 'annotation'].includes(message.action)) return;
  if (message.action === 'wake') { respond({ ok: true }); return; }
  var controller = new AbortController();
  var timeout = setTimeout(function () { controller.abort(); }, 4000);
  fetch('http://127.0.0.1:9223/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Weread-Input': 'v8' },
    body: JSON.stringify({ action: message.action }),
    signal: controller.signal
  }).then(function (response) {
    if (!response.ok) throw new Error('Input service unavailable');
    return response.json();
  }).then(function (result) {
    clearTimeout(timeout); respond(result);
  }).catch(function (error) {
    clearTimeout(timeout); respond({ ok: false, error: error.message });
  });
  return true;
});
