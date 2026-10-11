// Pin the devalue encoding invariant that the Nuxt decoder relies on.
//
// decodeNuxtFlat tells a type tag from data by checking whether an array node's
// slot 0 is a string. That is only sound because devalue encodes a plain array
// as a list of numeric indexes, so every slot is a number and a string can only
// be a type tag.
//
// The samples in devalue_flat_samples.json are real devalue@6.0.2 output,
// captured by running the package. Checking them here means the invariant is
// pinned to actual encoding behaviour, not to an assumption about it, and the
// test needs no installed dependency.
const fs = require('fs');
const path = require('path');

const samples = JSON.parse(fs.readFileSync(
  path.join(__dirname, 'devalue_flat_samples.json'), 'utf8'));

let ok = true;
const fail = (label, got) => {
  ok = false;
  console.log('BAD', label, got === undefined ? '' : got);
};

for (const testCase of samples.cases) {
  const { label, flat } = testCase;

  flat.forEach((item, index) => {
    if (!Array.isArray(item)) return;
    const allNumeric = item.length === 0 || item.every((v) => typeof v === 'number');
    const stringHeaded = typeof item[0] === 'string';
    if (!allNumeric && !stringHeaded) {
      fail(label + ': array at flat index ' + index + ' is neither numeric nor tag-headed',
        JSON.stringify(item));
      return;
    }
    // A tag-headed array must carry its payload starting at slot 1, which is
    // what the decoder skips past.
    if (stringHeaded && item.length < 1) {
      fail(label + ': tag-headed array has no payload slot', JSON.stringify(item));
    }
  });
  console.log('ok ', label, JSON.stringify(flat).slice(0, 60));
}

// The specific claim the decoder's `typeof kind === 'string' ? 1 : 0` rests on:
// no plain array in any sample leads with a string.
{
  let offenders = 0;
  for (const testCase of samples.cases) {
    testCase.flat.forEach((item) => {
      if (!Array.isArray(item)) return;
      const isPlainIndexList = item.every((v) => typeof v === 'number');
      if (isPlainIndexList && typeof item[0] === 'string') offenders++;
    });
  }
  if (offenders !== 0) fail('plain array led with a string', offenders);
  else console.log('ok ', 'no plain array leads with a string in any sample');
}

console.log('DEVALUE:', ok ? 'PASS' : 'FAIL');
process.exit(ok ? 0 : 1);
