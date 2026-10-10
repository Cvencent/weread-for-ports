"""Regressions for discovery navigation and visible transition feedback."""
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device import connect, evaluate
from e2e import press, selected, wait_for


class DiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.client = connect()
        evaluate(self.client, """sessionStorage.removeItem('wr-hh-loading');
          sessionStorage.removeItem('wr-hh-return-key');
          sessionStorage.removeItem('wr-hh-discovery-return');
          window.__discoveryOldDocument=true;location.href='/web/shelf';void 0""")
        wait_for(self.client, """!window.__discoveryOldDocument && location.pathname==='/web/shelf' &&
          !!document.querySelector('#wr-hh-nav .wr-hh-tab.wr-hh-focus') &&
          !!document.querySelector('.shelfBook') && !document.querySelector('#wr-hh-loading')""")

    def tearDown(self):
        wait_for(self.client, "document.readyState==='complete' && !document.querySelector('#wr-hh-loading')")
        self.client.close()

    def test_switch_has_immediate_loading_feedback(self):
        result = evaluate(self.client, """(function(){
          document.querySelector('#wr-hh-nav [data-i="1"]').click();
          var load=document.querySelector('#wr-hh-loading');
          return !!load && load.getAttribute('role')==='status' && load.getBoundingClientRect().height>20;
        })()""")
        self.assertTrue(result, "Navigation gives no loading feedback before leaving the shelf")

    def test_discovery_starts_with_recommendations_and_separate_top_tabs(self):
        evaluate(self.client, "document.querySelector('#wr-hh-nav [data-i=\"1\"]').click();void 0")
        wait_for(self.client, "location.pathname==='/' && !!document.querySelector('.wr_suggestion_card_wrapper')")
        time.sleep(1)
        result = evaluate(self.client, """(function(){
          var tabs=Array.from(document.querySelectorAll('#wr-hh-nav [data-discovery]')).map(e=>e.innerText);
          var books=Array.from(document.querySelectorAll('.wr_suggestion_card_wrapper'));
          return {tabs:tabs,books:books.length,complete:books.filter(e=>{var r=e.getBoundingClientRect();
            return r.width>30&&r.top>=100&&r.bottom<=innerHeight;}).length,
            shelfHidden:document.querySelector('.wr_index_mini_shelf_wrapper').getBoundingClientRect().height===0};
        })()""")
        self.assertEqual(result['tabs'], ['猜你喜欢', '榜单', '分类'])
        self.assertEqual(result['complete'], 4)
        self.assertTrue(result['shelfHidden'])
        self.assertTrue(evaluate(self.client, """Array.from(document.querySelectorAll('.wr_suggestion_card_wrapper')).every(e=>{
          var card=e.getBoundingClientRect(),info=e.querySelector('.wr_suggestion_card_content_info').getBoundingClientRect();
          var reason=e.querySelector('.wr_suggestion_card_content_reason').getBoundingClientRect();
          return info.top>=card.top&&info.bottom<=card.bottom&&reason.height>10;
        })"""), 'Recommendation reasons overflow their cards')

    def test_rank_subtabs_open_different_full_lists(self):
        evaluate(self.client, "location.href='/web/category/rising';void 0")
        wait_for(self.client, "!!document.querySelector('#wr-hh-nav .wr-hh-filters button') && !!document.querySelector('.wr_bookList_item')")
        self.assertTrue(evaluate(self.client, "document.querySelector('#wr-hh-nav [data-i=\"1\"]').classList.contains('on')"))
        self.assertTrue(evaluate(self.client, """Array.from(document.querySelectorAll('#wr-hh-nav [data-discovery]')).every(e=>{
          var r=e.getBoundingClientRect(),filters=document.querySelector('.wr-hh-filters').getBoundingClientRect();
          return r.width>=100&&r.height>=40&&r.bottom<=filters.top&&r.left>=0&&r.right<=innerWidth;
        })"""), "Rank filters collapse or cover the discovery tabs")
        for slug in ['newbook', 'all']:
            evaluate(self.client, f"document.querySelector('#wr-hh-nav [data-href=\"/web/category/{slug}\"]').click();void 0")
            wait_for(self.client, f"""location.pathname==='/web/category/{slug}' &&
              !!document.querySelector('.wr_bookList_item') && !document.querySelector('#wr-hh-loading') &&
              !!document.querySelector('#wr-hh-nav [data-href="/web/category/{slug}"]')""")
            self.assertTrue(evaluate(self.client, f"document.querySelector('#wr-hh-nav [data-href=\"/web/category/{slug}\"]').getAttribute('aria-selected')==='true'"))
            self.assertTrue(evaluate(self.client, "document.documentElement.scrollWidth<=innerWidth+1"))

    def test_categories_show_real_destinations_and_back_to_category_overview(self):
        evaluate(self.client, "document.querySelector('#wr-hh-nav [data-i=\"1\"]').click();void 0")
        wait_for(self.client, "!!document.querySelector('#wr-hh-nav [data-discovery=\"categories\"]')")
        evaluate(self.client, "document.querySelector('#wr-hh-nav [data-discovery=\"categories\"]').click();void 0")
        wait_for(self.client, "!!document.querySelector('#wr-hh-categories a')")
        self.assertGreaterEqual(evaluate(self.client, "document.querySelectorAll('#wr-hh-categories a').length"), 20)
        evaluate(self.client, "document.querySelector('#wr-hh-categories a[href=\"/web/category/200000\"]').click();void 0")
        wait_for(self.client, "location.pathname==='/web/category/200000' && !!document.querySelector('.wr_bookList_item') && !!document.querySelector('#wr-hh-nav [data-discovery=\"categories\"]')")
        self.assertTrue(evaluate(self.client, "document.querySelector('#wr-hh-nav [data-discovery=\"categories\"]').getAttribute('aria-selected')==='true'"))
        evaluate(self.client, "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}));void 0")
        wait_for(self.client, "location.pathname==='/' && !!document.querySelector('#wr-hh-categories a') && document.body.dataset.wrHhDiscovery==='categories'")

    def test_rank_return_restoration_does_not_override_next_navigation(self):
        evaluate(self.client, "window.__rankOldDocument=true;location.href='/web/category/rising';void 0")
        wait_for(self.client, """!window.__rankOldDocument &&
          !!document.querySelector('.wr_bookList_item') &&
          !!document.querySelector('#wr-hh-nav [data-discovery="ranks"].wr-hh-focus')""")
        evaluate(self.client, """(function(){
          var item=document.querySelector('.wr_bookList_item');
          var book=item.matches('a[href]')?item:item.querySelector('a[href*="/web/reader/"]');
          sessionStorage.setItem('wr-hh-discovery-return','h:'+new URL(book.href).pathname);
          window.__rankOldDocument=true;location.reload();
        })()""")
        wait_for(self.client, "!window.__rankOldDocument && !!document.querySelector('.wr_bookList_item.wr-hh-focus')")
        restored = selected(self.client)
        press(self.client, 'up')
        moved = selected(self.client)
        self.assertNotEqual(moved, restored, "Restored rank book cannot release focus to navigation")
        evaluate(self.client, """(function(){
          var node=document.createElement('span');
          document.querySelector('.ranking_page_header').appendChild(node);node.remove();
        })()""")
        time.sleep(2.5)
        self.assertEqual(selected(self.client), moved,
                         "Page refresh pulled focus back to the restored rank book")


if __name__ == '__main__':
    unittest.main()
