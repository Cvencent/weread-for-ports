import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class NavigationContractTests(unittest.TestCase):
    def test_discovery_navigation_uses_same_document_content_swap(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("wr-hh-same-document", js)
        self.assertIn("history.pushState", js)
        self.assertIn("fetch(target.href", js)
        self.assertIn("var isHome = target.pathname === '/';", js)
        self.assertIn("var marker = 'class=\"wr_index_page_content_wrapper';", js)
        self.assertIn("go(filter.dataset.href);", js)

    def test_latest_navigation_owns_loading_state(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("var loadingState = null, loadingTimer = null, navigationId = 0;", js)
        self.assertIn("var requestId = ++navigationId;", js)
        self.assertIn("requestId !== navigationId", js)
        self.assertIn("sameDocumentNavigate(href, requestId)", js)
        self.assertIn("closest('[data-href]')", js)
        self.assertIn("event.preventDefault()", js)
        self.assertIn("event.stopPropagation()", js)
        self.assertIn("stopImmediatePropagation", js)

    def test_top_navigation_works_when_nav_exists_before_sync(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("var tab = target.closest", js)
        self.assertIn("if (item.search) openSearch();", js)
        self.assertIn("else go(item.h);", js)
        self.assertIn("if (shellTab) { activateTab(shellTab);", js)

    def test_route_changes_restore_focus_to_primary_navigation(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("primaryTab", js)
        self.assertIn("wr-hh-tab.on", js)
    def test_same_document_navigation_restores_the_clicked_route_control(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        # focusFirst() still looks the key up and focuses it, but through one
        # `remembered` binding rather than two redeclared ones.
        block = js.split("function focusFirst() {", 1)[1].split("\n  }", 1)[0]
        self.assertIn("findByKey(focusKey)", block)
        self.assertIn("if (remembered) { focusAtEl(remembered); return; }", block)
        declarations = [line for line in block.splitlines()
                        if line.strip().startswith("var remembered")]
        self.assertEqual(len(declarations), 1,
                         "focusFirst redeclares `remembered`, which hoists and "
                         "makes the first lookup depend on declaration order")

    def test_rank_list_text_and_rating_badge_have_readable_shell_styles(self):
        css = (ROOT / "extension/shell.css").read_text(encoding="utf-8")
        self.assertIn("font-size: 15px !important; line-height: 20px !important; font-weight: 600 !important; color: var(--hh-ink) !important;", css)
        self.assertIn(".wr_bookList_item_reading_percent { color: var(--hh-green) !important; font-weight: 600 !important; }", css)
        self.assertIn(".book_rating_item_label_number_image { width: auto !important; height: 22px !important; max-width: 60px !important;", css)

    def test_discovery_subnav_buttons_are_wired_to_discovery_modes(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("closest('#' + NAV + ' [data-discovery]')", js)
        self.assertIn("setDiscovery(section.dataset.discovery)", js)

    def test_suggestion_refresh_cycles_rendered_books_and_keeps_links(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("function extractSuggestionBooks", js)
        self.assertIn("function nextSuggestions", js)
        self.assertIn("suggestionIndex", js)
        self.assertIn("/web/reader/", js)

    def test_suggestion_refresh_clears_restored_snapshot(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("clearSuggestions();", js)
        self.assertIn("otherwise the old", js)

    def test_suggestion_refresh_is_primed_on_cold_start(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("function primeSuggestions", js)
        self.assertIn("getElementById('__NUXT_DATA__')", js)
        self.assertIn("primeSuggestions();", js)

    def test_discovery_refresh_control_matches_rendered_markup(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn(
            ".wr_index_page_top_section_content_title .wr_index_page_top_section_header_action_link",
            js,
        )

    def test_boot_clears_stale_redirect_cookie(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("free_go_proxy", js)

    def test_discovery_tab_resets_to_recommendations(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("if (item.h === '/') {", js)
        self.assertIn("discoveryMode = 'suggestions';", js)

    def test_discovery_routes_prefer_the_active_section_focus(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("var sectionTab", js)
        self.assertIn("focusAtEl(inDiscovery ? (sectionTab || primaryTab) : (primaryTab || sectionTab));", js)

    def test_route_focus_keeps_its_scroll_container_visible(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("var route = document.getElementById('wr-hh-route-view');", js)
        self.assertIn("var routeRect = rc(route);", js)
        self.assertIn("route.scrollTop +=", js)

    def test_rank_return_restores_pending_focus(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("if (pendingOriginKey && (location.pathname === '/' || /^\\/web\\/category\\//.test(location.pathname))) {", js)


    def test_focus_reanchor_polling_runs_outside_overlays(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertNotIn("if (!menuEl() && !kbdVisible() && !openPanel()) { syncRetry(); return; }", js)
        self.assertIn("if (!menuEl() && !kbdVisible()) {\n        if (syncRetry()) return;", js)


    def test_reader_state_ignores_hidden_stale_containers(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        # The reader route still decides on its own, and every container is
        # checked for visibility, so a hidden stale node cannot mask the live one.
        self.assertIn("if (/\\/web\\/reader\\//.test(location.pathname)) return true;", js)
        self.assertIn("$$('.wr_horizontalReader,.readerChapterContent_container')", js)
        self.assertIn("for (var i = 0; i < found.length; i++) if (shown(found[i])) return true;", js)

    def test_same_document_route_layer_is_visible_for_every_supported_view(self):
        js = (ROOT / "extension/content.js").read_text(encoding="utf-8")
        self.assertIn("if (root) root.hidden = true;\n      host.hidden = false;", js)


if __name__ == "__main__":
    unittest.main()
