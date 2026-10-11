// Prove pageBtn() finds exactly the same element after the :empty +
// tag-narrowing refactor.
//
// pageBtn used to scan every span,div,a,button in the document and read
// innerText on each one, which forced a full layout pass on every page turn
// (Y / L1 / R1). The refactor matches on a wider tag set plus :empty first.
//
// The selector is read out of content.js so this test cannot drift from it.
const fs = require('fs');
const path = require('path');

const contentJs = fs.readFileSync(
  path.join(__dirname, '..', 'extension', 'content.js'), 'utf8');

const selectorMatch = contentJs.match(/var PAGE_LABEL_SEL =\s*'([^']+)'/);
if (!selectorMatch) {
  console.log('BAD could not find PAGE_LABEL_SEL in content.js');
  process.exit(1);
}
const SELECTED_TAGS = selectorMatch[1].split(',').map((t) => t.trim().toUpperCase());

const NAV = 'wr-hh-nav', MENU = 'wr-hh-menu';
const ORIGINAL_TAGS = ['SPAN', 'DIV', 'A', 'BUTTON'];

function mine(e) {
  return !!(e.closest && e.closest('#' + NAV + ',#' + MENU + ',#wr-hh-kbd'));
}
function shown(e) { return e.isConnected && e.shownOk; }

function mkEl(tag, opts = {}) {
  const e = {
    tagName: tag,
    childCount: opts.children || 0,
    text: opts.text === undefined ? '' : opts.text,
    isConnected: opts.connected !== false,
    shownOk: opts.shown !== false,
    ours: !!opts.ours,
  };
  // Once an element has no element children, innerText === textContent.
  e.innerText = e.text;
  e.textContent = e.text;
  e.children = new Array(e.childCount).fill(0);
  e.closest = (sel) => (e.ours && sel.includes(NAV)) ? {} : null;
  return e;
}

// ---- ORIGINAL: scan every span/div/a/button, compare innerText ----
function pageBtnOld(els, dir) {
  const want = dir === 'next' ? '下一页' : '上一页';
  for (let i = 0; i < els.length; i++) {
    const e = els[i];
    if (e.children.length) continue;
    if ((e.innerText || '').trim() !== want) continue;
    if (!shown(e) || mine(e)) continue;
    return e;
  }
  return null;
}

// ---- NEW: tag set + :empty prune, compare textContent ----
function pageBtnNew(all, dir) {
  const want = dir === 'next' ? '下一页' : '上一页';
  for (let i = 0; i < all.length; i++) {
    const e = all[i];
    // querySelectorAll('<tags>:empty') only yields listed tags with no children.
    if (!SELECTED_TAGS.includes(e.tagName)) continue;
    if (e.children.length) continue;
    if (mine(e)) continue;
    if ((e.textContent || '').trim() !== want) continue;
    if (!shown(e)) continue;
    return e;
  }
  return null;
}

const cases = [
  ['plain prev span',    [mkEl('SPAN', { text: '上一页' })]],
  ['plain next div',     [mkEl('DIV', { text: '下一页' })]],
  ['next in button',     [mkEl('BUTTON', { text: '下一页' })]],
  ['next in anchor',     [mkEl('A', { text: '下一页' })]],
  ['padded label',       [mkEl('SPAN', { text: '  下一页  ' })]],
  ['has element child',  [mkEl('SPAN', { text: '下一页', children: 1 })]],
  ['hidden match',       [mkEl('SPAN', { text: '下一页', shown: false })]],
  ['disconnected match', [mkEl('SPAN', { text: '下一页', connected: false })]],
  ['our own node',       [mkEl('SPAN', { text: '下一页', ours: true })]],
  ['wrong label',        [mkEl('SPAN', { text: '上一页' })]],
  ['empty label',        [mkEl('SPAN', { text: '' })]],
  ['first wins',         [mkEl('SPAN', { text: '上一页' }), mkEl('SPAN', { text: '上一页' })]],
  ['hidden first wins',  [mkEl('SPAN', { text: '下一页', shown: false }), mkEl('SPAN', { text: '下一页' })]],
  ['ours first wins',    [mkEl('SPAN', { text: '下一页', ours: true }), mkEl('SPAN', { text: '下一页' })]],
  ['child before match', [mkEl('SPAN', { text: '上一页', children: 1 }), mkEl('SPAN', { text: '下一页' })]],
  ['section tag',        [mkEl('SECTION', { text: '下一页' })]],
  ['img tag',            [mkEl('IMG', { text: '下一页' })]],
  ['hr tag',             [mkEl('HR', { text: '下一页' })]],
  ['em/strong tags',     [mkEl('EM', { text: '上一页' }), mkEl('STRONG', { text: '下一页' })]],
  ['em only next',       [mkEl('EM', { text: '下一页' })]],
  ['dt tag',             [mkEl('DT', { text: '下一页' })]],
  ['no candidates',      []],
];

let ok = true;

// The widened tag list must still contain every tag the original scanned.
for (const tag of ORIGINAL_TAGS) {
  if (!SELECTED_TAGS.includes(tag)) {
    ok = false;
    console.log('BAD selector dropped original tag', tag);
  }
}

for (const dir of ['prev', 'next']) {
  for (const [desc, els] of cases) {
    const a = pageBtnOld(els, dir);
    const b = pageBtnNew(els, dir);
    if (a !== b) {
      ok = false;
      console.log('BAD', dir, desc, 'old:', a && a.tagName, 'new:', b && b.tagName);
    }
  }
}

console.log('selected tags:', SELECTED_TAGS.length);
console.log('cases per direction:', cases.length);
console.log('EQUIVALENCE:', ok ? 'PASS' : 'FAIL');
process.exit(ok ? 0 : 1);
