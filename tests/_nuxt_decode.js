// Extract decodeNuxtFlat from content.js and exercise its tag handling.
//
// __NUXT_DATA__ uses devalue's flat format: the array holds every value once
// and references between them are indexes. A plain array is therefore encoded
// as a list of numeric indexes, so element 0 of an untagged array is always a
// number. A leading string can only be one of devalue's type tags, which is
// exactly what the decoder branches on.
//
// Regression under test: an unrecognised tag used to be pushed into the
// decoded list as a phantom element 0, silently shifting every real value.
const fs = require('fs');
const path = require('path');

const contentJs = fs.readFileSync(
  path.join(__dirname, '..', 'extension', 'content.js'), 'utf8');

const start = contentJs.indexOf('function decodeNuxtFlat(text) {');
const end = contentJs.indexOf('function suggestionBooksFromData(text) {');
if (start < 0 || end < 0) { console.log('BAD could not locate decodeNuxtFlat'); process.exit(1); }

const decodeNuxtFlat = eval('(' + contentJs.slice(start, end) + ')');

const show = (v) => JSON.stringify(v);
let ok = true;
const check = (cond, label, got) => {
  if (!cond) { ok = false; console.log('BAD', label, got === undefined ? '' : got); }
  else console.log('ok ', label, got === undefined ? '' : got);
};
const decode = (flat) => decodeNuxtFlat(show(flat)).value(0);

// Strings live at their own index; arrays reference them numerically.
check(show(decode([[1], 'hello'])) === '["hello"]',
  'array of indexes resolves', show(decode([[1], 'hello'])));
check(show(decode([[1, 2], 'v', { k: 3 }, 'w'])) === '["v",{"k":"w"}]',
  'mixed array resolves in order', show(decode([[1, 2], 'v', { k: 3 }, 'w'])));
check(show(decode([[]])) === '[]', 'empty array root', show(decode([[]])));

// Objects resolve each property through the index table.
check(show(decode([{ data: 1 }, { x: 2 }, 42])) === '{"data":{"x":42}}',
  'object resolves property indexes', show(decode([{ data: 1 }, { x: 2 }, 42])));

// Primitive roots are literals.
check(decode([5]) === 5, 'numeric root literal', decode([5]));
check(decode([null]) === null, 'null root literal', decode([null]));
check(decode(['s']) === 's', 'string root literal', decode(['s']));

// Known devalue tags unwrap to their payload index.
check(show(decode([["Reactive", 1], { a: 2 }, 7])) === '{"a":7}',
  'Reactive unwrap', show(decode([["Reactive", 1], { a: 2 }, 7])));
check(show(decode([["ShallowReactive", 1], { a: 2 }, 7])) === '{"a":7}',
  'ShallowReactive unwrap', show(decode([["ShallowReactive", 1], { a: 2 }, 7])));
check(show(decode([["Ref", 1], { b: 2 }, 8])) === '{"b":8}',
  'Ref unwrap', show(decode([["Ref", 1], { b: 2 }, 8])));
check(show(decode([["Reactive", 1], ["Ref", 2], { c: 3 }, 9])) === '{"c":9}',
  'nested wrapper unwrap', show(decode([["Reactive", 1], ["Ref", 2], { c: 3 }, 9])));

check(decode([["EmptyRef"]]) === null, 'EmptyRef -> null');
check(show(decode([["Set", 1], [10, 20], 11, 22])) === '[]',
  'Set -> []', show(decode([["Set", 1], [10, 20], 11, 22])));
check(show(decode([["Map", 1], [["k", 2], 3], 4, 5, 6])) === '{}',
  'Map -> {}', show(decode([["Map", 1], [["k", 2], 3], 4, 5, 6])));

// The regression: an unknown tag must not leak its name as element 0.
const unknown = decode([["SomeFutureTag", 1], { a: 2 }, 3]);
check(show(unknown) === '[{"a":3}]',
  'unknown tag skips itself, keeps payload', show(unknown));
check(show(unknown).indexOf('SomeFutureTag') < 0,
  'unknown tag name never appears in the decoded value', show(unknown));

// An unknown tag pointing at a list keeps every element of that list.
const unknownList = decode([["Date", 1], [2, 3], 'a', 'b']);
check(show(unknownList) === '[["a","b"]]',
  'unknown tag over a list keeps every element', show(unknownList));

// Known tags stay recognised after the change.
check(show(decode([["Reactive", 1], { a: 2 }, 7])) === '{"a":7}',
  'known tags still unwrap');

// Cycles terminate instead of recursing forever.
const cyclic = [{ self: 1 }];
cyclic.push(cyclic[0]);
try {
  check(true, 'cyclic payload terminates',
    show(decodeNuxtFlat(show(cyclic)).value(0)));
} catch (e) {
  check(false, 'cyclic payload terminates', e.message);
}

check(decodeNuxtFlat(show([])).value(99) === undefined,
  'out-of-range index -> undefined');

console.log('DECODE:', ok ? 'PASS' : 'FAIL');
process.exit(ok ? 0 : 1);
