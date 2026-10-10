"""Verify actual gamepad recommendations, rank tabs and category navigation."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device import connect, evaluate
from e2e import OUT, capture, press, wait_for, selected

client = connect()
evidence = {}
try:
    evaluate(client, "sessionStorage.removeItem('wr-hh-return-key');sessionStorage.removeItem('wr-hh-discovery-return');window.__discoveryOldDocument=true;location.href='/web/shelf';void 0")
    wait_for(client, "!window.__discoveryOldDocument && !!document.querySelector('#wr-hh-nav .wr-hh-tab.wr-hh-focus') && !!document.querySelector('.shelfBook')")
    press(client, 'right')
    press(client, 'a')
    wait_for(client, "!!document.querySelector('#wr-hh-nav [data-discovery=\"suggestions\"].wr-hh-focus') && !document.querySelector('#wr-hh-loading')")
    capture(client, 'v9-discovery.png')
    for _ in range(3):
        press(client, 'down')
        if evaluate(client, "!!document.querySelector('.wr_suggestion_card_wrapper.wr-hh-focus')"):
            break
    book = selected(client)
    assert book and '/web/reader/' in book['href'], book
    batch = evaluate(client, "Array.from(document.querySelectorAll('.wr_suggestion_card_wrapper')).filter(e=>e.getBoundingClientRect().height>20).map(e=>new URL(e.href).pathname)")
    press(client, 'a')
    wait_for(client, "location.pathname.includes('/web/reader/') && !!document.querySelector('.readerChapterContent canvas') && !document.querySelector('#wr-hh-loading')", 40)
    press(client, 'b')
    wait_for(client, "location.pathname==='/' && !!document.querySelector('.wr_suggestion_card_wrapper.wr-hh-focus') && !document.querySelector('#wr-hh-loading')")
    returned = selected(client)
    assert returned['href'] == book['href'], {'book':book,'returned':returned}
    restored = evaluate(client, "Array.from(document.querySelectorAll('.wr_suggestion_card_wrapper')).filter(e=>e.getBoundingClientRect().height>20).map(e=>new URL(e.href).pathname)")
    assert restored == batch, {'before':batch,'returned':restored}
    evidence['recommendedBookReturn'] = returned
    evidence['recommendationBatchRestored'] = restored
    capture(client, 'v9-discovery-return.png')
    evaluate(client, "document.querySelector('.wr_index_page_top_section_content_title .wr_index_page_top_section_header_action_link').click();void 0")
    wait_for(client, "!document.querySelector('#wr-hh-suggestions') && !document.body.hasAttribute('data-wr-hh-snapshot') && document.querySelectorAll('.wr_suggestion_card_wrapper').length===4")
    evidence['changeBatchClearsSnapshot'] = True
    # Reload a canonical entry to avoid depending on the last book's geometry.
    evaluate(client, "window.__discoveryOldDocument=true;location.reload();void 0")
    wait_for(client, "!window.__discoveryOldDocument && !!document.querySelector('#wr-hh-nav [data-discovery=\"suggestions\"].wr-hh-focus')")
    press(client, 'right')
    press(client, 'a')
    wait_for(client, "location.pathname==='/web/category/rising' && !!document.querySelector('#wr-hh-nav [data-discovery=\"ranks\"].wr-hh-focus') && !document.querySelector('#wr-hh-loading')")
    press(client, 'down')
    rank = evaluate(client, "document.querySelector('.wr-hh-focus').dataset.href")
    assert rank and '/web/category/' in rank, rank
    press(client, 'a')
    wait_for(client, f"""location.pathname==={json.dumps(rank)} &&
      !!document.querySelector('.wr_bookList_item') &&
      !!document.querySelector('#wr-hh-nav [data-discovery="ranks"].wr-hh-focus') &&
      !document.querySelector('#wr-hh-loading')""")
    capture(client, 'v9-ranks.png')
    assert '/web/category/' in rank
    evidence['gamepadRank'] = rank
    # B returns the overview; then choose the category top tab.
    press(client, 'b')
    wait_for(client, "location.pathname==='/' && !!document.querySelector('#wr-hh-nav [data-discovery=\"suggestions\"].wr-hh-focus') && !document.querySelector('#wr-hh-loading')")
    press(client, 'right')
    press(client, 'right')
    press(client, 'a')
    wait_for(client, "!!document.querySelector('#wr-hh-categories a') && document.body.dataset.wrHhDiscovery==='categories'")
    capture(client, 'v9-categories.png')
    press(client, 'down')
    category = selected(client)
    assert '/web/category/' in category['href'], category
    press(client, 'a')
    wait_for(client, "!!document.querySelector('.wr_bookList_item') && !!document.querySelector('#wr-hh-nav [data-discovery=\"categories\"].wr-hh-focus') && !document.querySelector('#wr-hh-loading')")
    capture(client, 'v9-category-books.png')
    evidence['gamepadCategory'] = category
    evidence['bounds'] = evaluate(client, "({width:document.documentElement.scrollWidth,viewport:innerWidth,header:document.querySelector('#wr-hh-nav').getBoundingClientRect().height})")
    assert evidence['bounds']['width'] <= evidence['bounds']['viewport'] + 1
    press(client, 'b')
    wait_for(client, "location.pathname==='/' && document.body.dataset.wrHhDiscovery==='categories'")
    press(client, 'b')
    wait_for(client, "location.pathname==='/web/shelf'")
    (OUT / 'v9-discovery-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS gamepad recommendation return, rank tabs, categories and category back')
finally:
    client.close()
