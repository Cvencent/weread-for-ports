// The refactored discoveryPayload() must extract exactly the same block as the
// original inline logic that used to live in sameDocumentNavigate().
const fs = require('fs');
const path = require('path');
const src = fs.readFileSync(path.join(__dirname, '..', 'extension', 'content.js'), 'utf8');

function extract(name){
  const start = src.indexOf('function '+name+'(');
  let i=src.indexOf('{',start), depth=0;
  for(let j=i;j<src.length;j++){ if(src[j]==='{')depth++; else if(src[j]==='}'){depth--; if(depth===0) return src.slice(start,j+1);} }
  throw new Error('missing '+name);
}

const oldImpl = `
function oldSlice(html){
  var marker2 = 'class="wr_index_page_content_wrapper';
  var start = html.indexOf(marker2);
  if (start < 0) return null;
  start = html.lastIndexOf('<div', start);
  var depth = 0, end = start, tag = /<\\/?div\\b[^>]*>/gi, match;
  tag.lastIndex = start;
  while ((match = tag.exec(html))) {
    if (match[0].charAt(1) === '/') depth--;
    else if (!/\\/\\s*>$/.test(match[0])) depth++;
    if (depth === 0) { end = tag.lastIndex; break; }
  }
  if (!end) return null;
  return html.slice(start, end);
}`;

const stubBooks = "function extractSuggestionBooks(){ return [{title:\"T\",href:\"/web/reader/a\"}]; }";
const body = [ stubBooks,
                extract('discoveryPayload'), oldImpl ].join('\n');
const impl = new Function(body + '\nreturn {discoveryPayload, oldSlice: oldSlice};')();

const html = [
 '<html><body><div id="app">',
 '<header>nav junk</header>',
 '<div class="wr_index_page_content_wrapper">',
   '<div class="wr_index_mini_shelf_wrapper"><a href="/web/reader/abc">Book</a></div>',
   '<div class="wr_index_page_top_section_content_suggestions">',
     '<div class="wr_suggestion_card_wrapper">Card one</div>',
   '</div>',
 '</div>',
 '<footer>footer junk</footer>',
 '</div>',
 '<script id="__NUXT_DATA__" type="application/json">[1,2,3]</script>',
 '</body></html>'
].join('\n');

const oldBlock = impl.oldSlice(html);
const p = impl.discoveryPayload(html);
console.log('old slice length:', oldBlock ? oldBlock.length : null);
console.log('new block length:', p ? p.block.length : null);
console.log('blocks identical:', oldBlock === p.block);
console.log('block head:', JSON.stringify(p.block.slice(0, 48)));
console.log('block tail:', JSON.stringify(p.block.slice(-24)));
if (oldBlock !== p.block) { console.log('EQUIVALENCE: FAIL'); process.exit(1); }

const noMark = '<html><body><div id="app">nothing</div></body></html>';
const a = impl.oldSlice(noMark), b = impl.discoveryPayload(noMark);
console.log('missing marker -> old:', a, ' new:', b);
if (a !== null || b !== null) { console.log('EQUIVALENCE: FAIL'); process.exit(1); }
console.log('EQUIVALENCE: PASS');
