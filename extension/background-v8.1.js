chrome.runtime.onMessage.addListener(function (message, sender, respond) {
  if (!message || message.type !== 'reader-input') return;
  if (!sender.url || !sender.url.startsWith('https://weread.qq.com/')) return;
  if (!['catalog', 'settings', 'activate', 'close', 'font-previous', 'font-next'].includes(message.action)) return;
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
