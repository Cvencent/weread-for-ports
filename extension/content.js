/* ============================================================
   微信读书 掌机外壳 — v9（分栏发现、加载恢复、沉浸阅读）

   ⭐ v6 相对 v5 的修复（依据 CDP 逐帧实测）：
     1. 【★致命★ 搜索框劫持导航】站方搜索框 <input.navBar_input> 被当成
        普通候选（书架页 idx0, gy=3），导致：
          · ↓ 从导航条直接跳到搜索框，跳过第一本书
          · 按 A 落在搜索框上 → 只聚焦、打不开书
          · 焦点视觉上是"空框"，用户报"按 A 没反应 / 不是每个都有蓝框"
        ⇒ v6【彻底排除文本输入类元素】不做导航候选；
           搜索改为掌机菜单里的显式入口 + 专属热键（START 短按）。
     2. 【Escape 被吞】typing() 为真时直接 return，连 Esc 都吃掉，
        用户被卡在输入框里出不来 ⇒ v6 允许 Esc 先 blur 再返回。
     3. 【候选为空无反馈】页面还在加载时按键无任何反应
        ⇒ v6 在 diag 里标注 empty 状态，并在首次按键时重试建表。
     4. 【菜单项增多】加入「搜索」，并支持 L1/R1 快速左右移动。

   ── 按键表（每个页面统一）──────────────────────────
     十字键      浏览页=网格导航 / 阅读器=翻页
     A           确认（进入、点击）
     B           返回（关浮层 → 退阅读器 → 上一级）
     X           目录
     Y           下一页
     L1 / R1     上一页 / 下一页（菜单内=左右移动）
     L2 / R2     页面顶部 / 底部；阅读器内=上一页 / 下一页
     SELECT      退出应用
     START       唤出掌机菜单（目录/设置/搜索/上一页/书架/退出）
     （阅读器内 A 只确认当前焦点；Start 才唤出菜单）
   ============================================================ */
(function () {
  'use strict';
  function readPendingLoading() {
    try {
      var pending = JSON.parse(sessionStorage.getItem('wr-hh-loading') || 'null');
      if (pending && pending.text && pending.text.indexOf('失败') < 0 && Date.now() - pending.started < 20000) return pending;
    } catch (x) {}
    return null;
  }
  function ensureBootMask() {
    var root = document.documentElement;
    if (!root) return;
    root.classList.remove('wr-hh-boot-ready');
    if (!document.getElementById('wr-hh-boot-mask')) {
      var mask = document.createElement('div');
      mask.id = 'wr-hh-boot-mask';
      mask.setAttribute('role', 'status');
      mask.setAttribute('aria-live', 'polite');
      mask.innerHTML = '<span class="wr-hh-spinner" aria-hidden="true"></span><strong></strong>';
      var label = mask.querySelector('strong');
      var pending = readPendingLoading();
      if (label) label.textContent = (pending && pending.text) || '正在加载微信读书';
      root.appendChild(mask);
    }
  }
  function releaseBootMask() {
    var root = document.documentElement;
    if (root) root.classList.add('wr-hh-boot-ready');
    var mask = document.getElementById('wr-hh-boot-mask');
    if (mask) mask.remove();
  }
  function setBootMaskText(text) {
    var mask = document.getElementById('wr-hh-boot-mask');
    if (!mask) return;
    var label = mask.querySelector('strong');
    if (label) label.textContent = text || '正在加载微信读书';
  }
  /* Warm DNS/TLS to the reader asset hosts before the reader document loads. */
  function ensurePreconnect() {
    var root = document.head || document.documentElement;
    if (!root) return;
    ['https://cdn.weread.qq.com', 'https://res.weread.qq.com', 'https://oss.weread.qq.com'].forEach(function (host) {
      if (document.querySelector('link[data-wr-hh-preconnect="' + host + '"]')) return;
      var link = document.createElement('link');
      link.setAttribute('rel', 'preconnect');
      link.setAttribute('href', host);
      link.setAttribute('crossorigin', 'anonymous');
      link.setAttribute('data-wr-hh-preconnect', host);
      root.appendChild(link);
    });
  }
  ensureBootMask();
  ensurePreconnect();

  /* The site loads a payment widget synchronously from midas.gtimg.cn in <head>.
     If that host stalls, the document never reaches body/DOMContentLoaded and
     the extension cannot receive any key input. Reload once after a generous
     timeout; sessionStorage prevents a reload loop. */
  (function guardHeadStall() {
    var key = 'wr-hh-head-stall-' + location.pathname;
    try { if (sessionStorage.getItem(key)) return; } catch (x) {}
    setTimeout(function () {
      if (document.readyState !== 'loading' || document.body) return;
      try { sessionStorage.setItem(key, '1'); } catch (x) {}
      window.location.reload();
    }, 12000);
  })();

  var FOCUS = 'wr-hh-focus';
  var NAV = 'wr-hh-nav';
  var MENU = 'wr-hh-menu';
  var ROWH = 28;            /* 分行容差（px） */

  function $(s, r) { return (r || document).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function rc(e) { return e.getBoundingClientRect(); }
  function mine(e) { return !!(e.closest && e.closest('#' + NAV + ',#' + MENU + ',#wr-hh-kbd')); }
  function typing() {
    var a = document.activeElement;
    if (!a) return false;
    var t = (a.tagName || '').toLowerCase();
    return t === 'input' || t === 'textarea' || a.isContentEditable;
  }

  /* ⭐ v6：文本输入类元素 —— 绝不作为导航候选
     站方搜索框 <input.navBar_input> 混进候选会造成：
       · ↓ 从导航条跳过第一本书
       · A 键落在它身上 → 只聚焦不进入
       · 视觉焦点是个"空框" ⇒ 用户感知为"按 A 没反应"
     搜索改由掌机菜单「搜索」项 + START 热键显式触发。            */
  function isTextish(e) {
    if (!e || !e.tagName) return false;
    var t = e.tagName.toUpperCase();
    if (t === 'INPUT' || t === 'TEXTAREA') return true;
    if (e.isContentEditable) return true;
    var ty = (e.getAttribute && e.getAttribute('type') || '').toLowerCase();
    if (t === 'INPUT' && !(/^(submit|button|reset|checkbox|radio|image)$/.test(ty))) return true;
    return false;
  }
  function isReader() {
    if (/\/web\/reader\//.test(location.pathname)) return true;
    /* The route check alone is not enough: a book can render its container
       lazily, and a previous chapter's container can linger behind it. Testing
       only the first match let a hidden stale container hide the visible one,
       which is enough to send navWanted/candidates/focusSweep down the browsing
       branch while the reader is actually on screen. */
    var found = $$('.wr_horizontalReader,.readerChapterContent_container');
    for (var i = 0; i < found.length; i++) if (shown(found[i])) return true;
    return false;
  }
  function hasNav() { return !!document.getElementById(NAV); }
  function menuEl() { return document.getElementById(MENU); }

  function shownSized(e, r) {
    var cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (parseFloat(cs.opacity || '1') < 0.04) return false;
    return true;
  }
  function shown(e) {
    if (!e || !e.isConnected) return false;
    var r = rc(e);
    if (r.width < 18 || r.height < 14) return false;
    return shownSized(e, r);
  }

  /* Cache vector data because the discovery page omits the site's sprite. */
  var iconAssets = {}, iconsCached = false;
  try { iconAssets = JSON.parse(sessionStorage.getItem('wr-hh-icon-assets-v8') || '{}'); } catch (x) {}
  if (!iconAssets || typeof iconAssets !== 'object' || Array.isArray(iconAssets)) iconAssets = {};
  function icon(name) {
    if (!iconsCached) {
      ['search', 'close', 'album', 'star', 'list', 'setting', 'arrow', 'article3'].forEach(function (id) {
        var symbol = document.getElementById(id);
        if (!symbol || symbol.tagName.toLowerCase() !== 'symbol') return;
        var paths = Array.from(symbol.querySelectorAll('path')).map(function (p) {
          return { d: p.getAttribute('d'), rule: p.getAttribute('fill-rule') };
        });
        if (paths.length) iconAssets[id] = { viewBox: symbol.getAttribute('viewBox'), paths: paths };
      });
      iconsCached = true;
      try { sessionStorage.setItem('wr-hh-icon-assets-v8', JSON.stringify(iconAssets)); } catch (x) {}
    }
    var asset = iconAssets[name], ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    svg.setAttribute('class', 'wr-hh-icon');
    svg.setAttribute('aria-hidden', 'true');
    if (asset && Array.isArray(asset.paths)) {
      svg.setAttribute('viewBox', String(asset.viewBox || '0 0 24 24'));
      asset.paths.forEach(function (item) {
        if (!item || typeof item.d !== 'string') return;
        var path = document.createElementNS(ns, 'path');
        path.setAttribute('d', item.d);
        if (item.rule === 'evenodd') path.setAttribute('fill-rule', 'evenodd');
        svg.appendChild(path);
      });
      return svg.outerHTML;
    }
    return '<svg class="wr-hh-icon" aria-hidden="true"><use href="#' + name + '"></use></svg>';
  }
  function showOverlay() {
    if ($('#wr-hh-overlay')) return;
    var overlay = document.createElement('div');
    overlay.id = 'wr-hh-overlay';
    overlay.addEventListener('click', function () { hideMenu(); hideKbd(); });
    document.body.appendChild(overlay);
  }
  function hideOverlay() {
    if (menuEl() || kbdVisible()) return;
    var overlay = $('#wr-hh-overlay');
    if (overlay) overlay.remove();
  }

  /* ================= 候选收集 ================= */
  var cache = null, cacheOk = false, invT = null;
  var focusEl = null;          /* ⭐ 用元素引用追踪焦点（索引会因缓存重建而错位） */

  function invalidateSoon() {
    if (invT) return;
    invT = setTimeout(function () { invT = null; cacheOk = false; }, 150);
  }
  function invalidateNow() { cacheOk = false; }

  /* 诊断（写入隐藏 DOM 节点，供远程读取；扩展在隔离世界，window 读不到） */
  function diag(o) {
    try {
      var d = document.getElementById('wr-diag');
      if (!d) {
        d = document.createElement('div');
        d.id = 'wr-diag';
        d.style.display = 'none';
        (document.body || document.documentElement).appendChild(d);
      }
      d.textContent = JSON.stringify(o);
    } catch (e) {}
  }

  var SEL = [
    'a[href]', 'button', '[role="button"]', 'input',
    '[class*="card"]', '[class*="item"]', '[class*="tab"]',
    '[class*="shelfBook"]', '.shelfArchive', '[class*="bookItem"]', '[class*="book_card"]',
    '.reader_font_control_slider_track',
    '[class*="chapter"]', '[class*="catalog"] li', '[class*="menu"] [class*="item"]'
  ].join(',');

  /* ⭐ 行分桶基准：以文档左上为原点（加 scrollY）⇒ 避免每次滚动后
       行号整体平移，导致"同一视觉行的元素被拆成不同行"。 */
  function rowOf(r) {
    return Math.round((r.top + r.height / 2 + window.scrollY) / ROWH);
  }

  function candidates() {
    if (cacheOk && cache) return cache;

    var activePanel = openPanel();
    var raw;
    if (activePanel && activePanel.matches('.readerCatalog')) raw = activePanel.querySelectorAll('.readerCatalog_list_item,.readerCatalog_list_item_inner');
    else if (activePanel) raw = activePanel.querySelectorAll(SEL);
    else if (loadingState) raw = document.querySelectorAll('#wr-hh-loading button');
    else if (document.body.classList.contains('body_search_show')) raw = document.querySelectorAll('.search_result a,.search_result button,.search_result [role="button"]');
    else if (location.pathname === '/web/shelf') raw = document.querySelectorAll('.shelfBook,.shelfArchive');
    else if (location.pathname === '/') raw = document.querySelectorAll('.wr_suggestion_card_wrapper,.wr_index_page_top_section_content_title .wr_index_page_top_section_header_action_link,#wr-hh-categories a');
    else if (/^\/web\/category\//.test(location.pathname)) raw = document.querySelectorAll('.wr_bookList_item,.ranking_page_header button,.ranking_page_header [role="button"]');
    else if (isReader()) raw = document.querySelectorAll('.chapterContentError .retry,.readerError button');
    else raw = document.querySelectorAll(SEL);
    var list = [];
    for (var i = 0; i < raw.length; i++) {
      var e = raw[i];
      if (activePanel && !activePanel.contains(e)) continue;
      if (activePanel && e.classList.contains('font-panel-content-fonts-tab')) continue;
      if (mine(e) && !e.matches('#' + NAV + ' .wr-hh-tab')) continue;
      if (isTextish(e)) continue;          /* ⭐ v6：排除搜索框等文本输入 */
      /* One layout read per candidate: shown() reuses the same rect for the
         size test below instead of forcing a second reflow. */
      if (!e.isConnected) continue;
      var r = rc(e);
      if (r.width < 18 || r.height < 14) continue;
      if (!shownSized(e, r)) continue;
      /* 排除"盖住大半屏"的容器（放宽到 0.60，避免误杀大卡片） */
      if (r.width * r.height > innerWidth * innerHeight * 0.60) continue;
      if (e.classList.contains('font-panel-content-fonts-item') &&
          !e.getAttribute('aria-label') && e.style.fontFamily) {
        e.setAttribute('aria-label', e.style.fontFamily.split(',')[0]
          .replace(/^['"]|['"]$/g, '').replace(/-min$/, '').trim());
      }
      list.push(e);
    }

    /* 只留最外层：祖先已在候选里则丢弃自己（避免书卡被拆成标题/作者） */
    var out = [], selectedSet = new Set(list);
    for (var j = 0; j < list.length; j++) {
      var el = list[j], keep = true;
      for (var p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        if (selectedSet.has(p)) { keep = false; break; }
      }
      if (keep) out.push(el);
    }

    /* 网格坐标：先算坐标，再排序；导航条行号为 -1（永远置顶）
       Tabs are tracked in a Set: on a long shelf both this merge and the
       coordinate pass used to be linear scans per element. */
    var tabs = activePanel ? [] : $$('#' + NAV + ' button');
    var inOut = new Set(out);
    var tabSet = new Set(tabs);
    for (var k = 0; k < tabs.length; k++) {
      if (shown(tabs[k]) && !inOut.has(tabs[k])) { out.push(tabs[k]); inOut.add(tabs[k]); }
    }
    for (var m = 0; m < out.length; m++) {
      var rr = rc(out[m]);
      var isTab = tabSet.has(out[m]);
      out[m].__gy = isTab ? Math.round(rr.top / ROWH) - 10 : rowOf(rr);
      out[m].__gx = rr.left + rr.width / 2;
    }
    out.sort(function (a, b) {
      return a.__gy !== b.__gy ? a.__gy - b.__gy : a.__gx - b.__gx;
    });

    cache = out; cacheOk = true;
    return cache;
  }

  function clearFx() {
    var o = $$('.' + FOCUS);
    for (var i = 0; i < o.length; i++) o[i].classList.remove(FOCUS);
  }

  /* 保证焦点元素可见（顶部有 52px 导航条） */
  function ensureVisible(el) {
    if (el.closest('#' + NAV)) {
      el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      return;
    }
    var route = document.getElementById('wr-hh-route-view');
    if (route && route.contains(el)) {
      var routeRect = rc(route);
      var routeItem = rc(el);
      if (routeItem.top < routeRect.top + 6) {
        route.scrollTop += routeItem.top - routeRect.top - 12;
      } else if (routeItem.bottom > routeRect.bottom - 6) {
        route.scrollTop += routeItem.bottom - routeRect.bottom + 12;
      }
      return;
    }
    var panel = openPanel();
    if (panel && panel.contains(el)) {
      el.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      var sticky = panel.querySelector('.font-panel-content_sticky');
      if (sticky && !sticky.contains(el)) {
        var r = rc(el), bottom = rc(sticky).bottom;
        if (r.top < bottom + 6) panel.scrollTop += r.top - bottom - 6;
      }
      return;
    }
    var top = hasNav() ? rc(document.getElementById(NAV)).bottom : 0;
    for (var i = 0; i < 4; i++) {
      var r = rc(el);
      if (r.top < top + 6) window.scrollBy(0, r.top - top - 12);
      else if (r.bottom > innerHeight - 6) window.scrollBy(0, r.bottom - innerHeight + 12);
      else break;
    }
  }

  function jumpEdge(dir) {
    var route = document.getElementById('wr-hh-route-view');
    var target = route && !route.hidden ? route : document.scrollingElement || document.documentElement;
    target.scrollTop = dir === 'top' ? 0 : target.scrollHeight;
    if (target !== document.scrollingElement && target !== document.documentElement) {
      window.scrollTo(0, dir === 'top' ? 0 : document.documentElement.scrollHeight);
    }
  }

  function focusAtEl(el) {
    var t = candidates();
    if (!t.length) return;           /* 空窗期：保持现有高亮，别清掉 */
    if (!el || t.indexOf(el) < 0) el = t[0];
    focusEl = el;
    focusKey = keyOf(el);            /* ⭐ 记录身份，供重渲染后重锚定 */
    clearFx();
    try { el.classList.add(FOCUS); } catch (e) {}
    ensureVisible(el);
    diag({ n: t.length, at: label(el), idx: t.indexOf(el) });
  }

  /* ⭐⭐ v7 焦点身份（应对站方虚拟化网格的重渲染）
     ⚠️ 书架页是「虚拟滚动网格」，每次滚动/重渲染都会重建 DOM 节点，
        导致 focusEl 变成游离节点 → 高亮消失、A 键失效。
     ⇒ 用 href/文本作为稳定身份，重渲染后按身份找回同一个逻辑条目。 */
  var focusKey = '';
  var pendingReturnKey = '', returnUntil = 0;
  function loadReturnKey() {
    if (location.pathname !== '/web/shelf') return;
    try { pendingReturnKey = sessionStorage.getItem('wr-hh-return-key') || ''; } catch (x) {}
    returnUntil = Date.now() + 15000;
  }
  function restoreBookFocus() {
    if (!pendingReturnKey || location.pathname !== '/web/shelf') return false;
    var book = findByKey(pendingReturnKey);
    if (book) {
      pendingReturnKey = '';
      focusAtEl(book);
      return true;
    }
    if (Date.now() >= returnUntil) pendingReturnKey = '';
    return false;
  }
  function keyOf(e) {
    if (!e) return '';
    var dataHref = e.getAttribute && e.getAttribute('data-href');
    var h = dataHref || e.getAttribute && e.getAttribute('href');
    var bookLink = !h && e.querySelector && e.querySelector('a[href*="/web/reader/"]');
    if (bookLink) h = bookLink.getAttribute('href');
    if (h) {
      try {
        var url = new URL(h, location.href);
        if (url.origin === location.origin) h = url.pathname + url.search + url.hash;
      } catch (x) {}
      return 'h:' + h;
    }
    return 't:' + label(e);
  }
  function findByKey(k) {
    if (!k) return null;
    var t = candidates();
    for (var i = 0; i < t.length; i++) { if (keyOf(t[i]) === k) return t[i]; }
    return null;
  }

  function focusAt(n) {
    var t = candidates();
    if (!t.length) return;
    if (n < 0) n = 0;
    if (n >= t.length) n = t.length - 1;
    focusAtEl(t[n]);
  }

  /* ⭐ 身份重锚：优先按 focusKey 找回，其次首项 */
  function reanchor() {
    invalidateNow();
    var e = findByKey(focusKey);
    if (e) { focusEl = e; clearFx();
      try { e.classList.add(FOCUS); } catch (x) {}
      return e; }
    if (focusEl && document.body.contains(focusEl)) return focusEl;
    focusAt(0);
    return focusEl;
  }

  function focusFirst() {
    if (isReader() && !openPanel()) { syncRetry(); return; }
    if (pendingOriginKey && (location.pathname === '/' || /^\/web\/category\//.test(location.pathname))) {
      var remembered = findByKey(pendingOriginKey);
      if (remembered) { focusAtEl(remembered); return; }
    }
    var remembered = findByKey(focusKey);
    if (remembered) { focusAtEl(remembered); return; }
    if (!focusEl || !focusEl.isConnected) {
      var primaryTab = $("#" + NAV + " .wr-hh-tab.on");
      var sectionTab = $("#" + NAV + " [data-discovery].on");
      var inDiscovery = location.pathname === '/' || /^\/web\/category\//.test(location.pathname);
      focusAtEl(inDiscovery ? (sectionTab || primaryTab) : (primaryTab || sectionTab));
    }
    else focusAtEl(focusEl);
  }

  /* ⭐⭐ v7 焦点锚定轮询
     ⚠️ 血泪：SPA 换页后目标页的 DOM 是【逐步渲染】的（图片/接口陆续到），
        固定延迟（如 1.4s）会撞上"还没渲染出候选元素"的空窗 ⇒
        焦点锚定失败 ⇒ 用户按 ↓ 完全没反应（实测复现）。
     ⇒ 改为高频轮询：每 300ms 试一次，一旦候选出现立刻锚定；最多试 15 次。 */
  var anchorTimer = null;
  function anchorFocus() {
    if (anchorTimer) return;
    var tries = 0;
    anchorTimer = setInterval(function () {
      tries++;
      invalidateNow();
      var t = candidates();
      if (t && t.length) {
        if (!restoreBookFocus()) {
          if (focusEl && focusEl.isConnected && t.indexOf(focusEl) >= 0) focusAtEl(focusEl);
          else focusFirst();
        }
        clearInterval(anchorTimer); anchorTimer = null;
        diag({ anchor: 'ok', n: t.length, tries: tries });
      } else if (tries >= 15) {
        clearInterval(anchorTimer); anchorTimer = null;
        diag({ anchor: 'give-up', tries: tries });
      }
    }, 300);
  }

  function label(e) {
    return (e.getAttribute('aria-label') || e.innerText || e.className || e.tagName)
      .toString().replace(/\s+/g, ' ').trim().slice(0, 80);
  }

  /* ⭐ v7 网格移动：改用【绝对文档坐标 + 对称判据】
     ⚠️ v6 用"按 ROWH 行分桶"存在致命不对称：
        页面懒加载/滚动后 __gy 整体漂移 ⇒ ↓↓ 之后再 ↑ 回不到原元素（实测复现）。
     现在：↓ 取「top 最近的在下方元素」，↑ 取「top 最近的上方元素」，
           ←→ 优先「同一视觉行（纵向重叠 ≥40%）内最近」，行内到头才跨行。
     这套判据与滚动位置无关，且天然对称（↓ 再 ↑ 必回原处）。 */
  function absTop(e) { return rc(e).top + window.scrollY; }
  function absLeft(e) { return rc(e).left + window.scrollX; }

  /* ⭐⭐ v7 关键：来向记忆（严格可逆导航）
     ⚠️ 纯几何网格【天然不可逆】：A、C 同一行且列距大，B 在下一行，
        A→↓→B 之后 B→↑ 会落到 C（因为 C 离 B 的水平距离比 A 近）。
        实测用户就卡在这：↓↓ 后再 ↑ 回不到原处。
     ⇒ 记录「从 X 向 dir 走到 Y」，则从 Y 向 opposite(dir) 必回 X。
       仅当记忆失效（元素已被移除）才回退到几何算法。 */
  var navFrom = new WeakMap();
  var OPP = { up: 'down', down: 'up', left: 'right', right: 'left' };
  function recordNav(from, dir, to) {
    var m = navFrom.get(to) || {};
    m[OPP[dir]] = from;
    navFrom.set(to, m);
  }

  function move(dir) {
    var t = candidates();
    /* ⚠️ 站方重渲染期间候选会瞬时为空 ⇒ 不能立刻放弃（否则按键被吞）。
       重试一次；仍为空则仅记诊断，保持现有焦点不动。 */
    if (!t.length) {
      invalidateNow();
      t = candidates();
      if (!t.length) { diag({ mv: dir, empty: true }); return; }
    }
    if (!focusEl || t.indexOf(focusEl) < 0) { focusAt(0); return; }

    var c = focusEl, cr = rc(c);

    /* ① 优先走「来向记忆」——保证 ↓↑ 严格对称 */
    var mem = navFrom.get(c);
    if (mem && mem[dir] && mem[dir].isConnected && t.indexOf(mem[dir]) >= 0) {
      var back = mem[dir];
      recordNav(c, dir, back);
      diag({ mv: dir, back: true, from: label(c), to: label(back) });
      focusAtEl(back);
      return;
    }
    /* ①b 记忆里的节点被重渲染换掉 → 按身份键找回 */
    if (mem && mem[dir] && (!mem[dir].isConnected || t.indexOf(mem[dir]) < 0)) {
      var alt = findByKey(keyOf(mem[dir]));
      if (alt) {
        recordNav(c, dir, alt);
        diag({ mv: dir, backByKey: true, to: label(alt) });
        focusAtEl(alt);
        return;
      }
    }
    /* ①c 自己在重渲染中变味 → 先按身份键把"当前"修复，重走一遍 */
    if (!document.body.contains(c) && focusKey) {
      var self = findByKey(focusKey);
      if (self && self !== c) { focusEl = self; focusKey = keyOf(self); move(dir); return; }
    }

    var ct = absTop(c), cb = ct + cr.height;
    var cl = absLeft(c), ccol = cl + cr.width / 2;
    var best = -1, bs = Infinity, i, r;
    /* One rect read per candidate per keypress: absTop/absLeft each call
       rc() again, so derive every coordinate from a single measurement. */

    if (dir === 'down' || dir === 'up') {
      for (i = 0; i < t.length; i++) {
        if (t[i] === c) continue;
        r = rc(t[i]); if (r.width < 1) continue;
        var top = r.top + window.scrollY, col = r.left + window.scrollX + r.width / 2;
        var d = (dir === 'down') ? (top - ct) : (ct - top);
        if (d <= 2) continue;                       /* 必须真的在下方/上方 */
        var sc = d * 1000 + Math.abs(col - ccol);   /* 主序=垂直距离，次序=横向偏差 */
        if (sc < bs) { bs = sc; best = i; }
      }
    } else {
      /* ←→：先只在「与本元素纵向重叠 ≥40%」的同行元素里找 */
      var bandBest = Infinity;
      for (i = 0; i < t.length; i++) {
        if (t[i] === c) continue;
        r = rc(t[i]); if (r.width < 1) continue;
        var top2 = r.top + window.scrollY, bot2 = top2 + r.height;
        var ov = Math.min(bot2, cb) - Math.max(top2, ct);
        if (ov < Math.min(r.height, cr.height) * 0.4) continue;
        var col2 = r.left + window.scrollX + r.width / 2;
        if (dir === 'right' && col2 <= ccol + 2) continue;
        if (dir === 'left'  && col2 >= ccol - 2) continue;
        var dist = Math.abs(col2 - ccol);
        if (dist < bandBest) { bandBest = dist; best = i; }
      }
      if (bandBest < Infinity) {
        /* The nearest same-row candidate was found; keep it. */
      } else {
        /* 行内到头 → 跨到相邻行的最左/最右（按行中心就近） */
        best = -1;
        for (i = 0; i < t.length; i++) {
          if (t[i] === c) continue;
          r = rc(t[i]); if (r.width < 1) continue;
          var top3 = r.top + window.scrollY, col3 = r.left + window.scrollX + r.width / 2;
          var dy = top3 - ct;
          if (dir === 'right' && dy <= 2) continue;
          if (dir === 'left'  && dy >= -2) continue;
          var sc2 = Math.abs(dy) * 1000 + (dir === 'right' ? col3 : -col3);
          if (sc2 < bs) { bs = sc2; best = i; }
        }
      }
    }

    if (best >= 0) {
      diag({ mv: dir, from: label(c), to: label(t[best]), n: t.length });
      recordNav(c, dir, t[best]);
      focusAtEl(t[best]);
      return;
    }

    /* 同轴无目标 → 小步滚动页面后重建候选并重新锚定（可滚动长页兜底）
       ⚠️ 步长必须小：240px 会一次滚过整屏导致"跳页感"且焦点易丢。 */
    var before = window.scrollY;
    if (dir === 'down') window.scrollBy(0, 90);
    else if (dir === 'up') window.scrollBy(0, -90);
    if (window.scrollY !== before) {
      invalidateNow();
      setTimeout(function () {
        invalidateNow();
        var t2 = candidates();
        if (!focusEl || !focusEl.isConnected || t2.indexOf(focusEl) < 0) focusAt(0);
        else focusAtEl(focusEl);
      }, 120);
    } else {
      diag({ mv: dir, from: label(c), stuck: true, n: t.length });
    }
  }

  /* ⭐ 激活：先确保可见，再点；若落在文本输入上则先脱离（防止键盘劫持） */
  function activate() {
    var t = candidates();
    if (!t.length) { diag({ act: 'empty' }); invalidateNow(); anchorFocus(); return; }

    /* ⚠️⚠️ 血泪：焦点元素被站方重渲染移除后，若这里只是 `focusAt(0); return;`
       就会【把这一次 A 键吃掉】—— 表现为用户反复按 A 都没反应。
       ⇒ v7：先用【身份键】找回同一个逻辑条目再执行；找不到才退回首项。 */
    if (!focusEl || !document.body.contains(focusEl) || t.indexOf(focusEl) < 0) {
      invalidateNow();
      var again = findByKey(focusKey);
      if (again) {
        focusEl = again;
        diag({ act: 're-anchored-by-key', at: label(again) });
      } else {
        diag({ act: 're-anchor-first' });
        focusAt(0);
        if (!focusEl) return;
      }
    }

    var el = focusEl;
    if (el.classList.contains('reader_font_control_slider_track')) return;
    if (isTextish(el)) {           /* 双保险：文本输入绝不主动聚焦 */
      try { el.blur(); } catch (e) {}
      diag({ act: 'skip-textish', tag: el.tagName });
      return;
    }
    ensureVisible(el);
    var shellTab = el.closest && el.closest('#' + NAV + ' .wr-hh-tab');
    if (shellTab) { activateTab(shellTab); invalidateSoon(); return; }
    var target = el;
    if (!(/^(A|BUTTON)$/.test(el.tagName) ||
          el.getAttribute('role') === 'button' || el.onclick)) {
      target = el.querySelector('a,button,[role="button"]') ||
               (el.closest && el.closest('a,button')) || el;
    }
    diag({ act: label(el), tag: el.tagName, targetTag: target.tagName,
           href: (target.getAttribute && target.getAttribute('href')) || '' });
    if (/\/web\/reader\//.test(target.getAttribute('href') || '')) {
      if (location.pathname === '/' && discoveryMode === 'suggestions') saveSuggestions(keyOf(el));
      try {
        sessionStorage.setItem('wr-hh-return-key', keyOf(el));
        sessionStorage.setItem('wr-hh-reader-origin', JSON.stringify({ href: location.pathname, key: keyOf(el), mode: discoveryMode }));
      } catch (x) {}
      beginLoading(target.getAttribute('href'), '正在打开书籍');
    } else if (/\/web\/category\//.test(target.getAttribute('href') || '')) {
      beginLoading(target.getAttribute('href'), '正在加载分类');
    }
    if (openPanel()) readerInput('activate');
    else try { target.click(); } catch (e) { diag({ actErr: String(e) }); }
    invalidateSoon();
  }

  /* ⭐ v6：显式搜索入口 —— 把焦点交给站方搜索框，并唤出【掌机自绘键盘】 */
  var INP_SEL = [
    '.search_input_text', '.wr_index_page_search_bar_input',
    'input[placeholder*="搜索"]', 'input[placeholder*="书名"]',
    'input[type="search"]', 'input[type="text"]'
  ];
  function findInput() {
    for (var i = 0; i < INP_SEL.length; i++) {
      var e = $(INP_SEL[i]);
      if (e && e.isConnected && shown(e)) return e;
    }
    return $('.navBar_input');
  }
  function openSearch() {
    var i = findInput();
    if (!i) { diag({ search: 'not-found' }); showHint('当前页面无法搜索，请返回书架重试'); return false; }
    document.body.classList.add('wr-hh-searching');
    kbdTarget = i;
    kbdBuf = i.value || '';
    try { i.focus(); i.click(); } catch (x) {}
    showKbd();
    diag({ search: 'opened', sel: i.className.toString().slice(0, 40) });
    return true;
  }

  /* ================= ⭐ 掌机自绘键盘 =================
     掌机无触屏、无鼠标指针、无中文输入法 ⇒ 用十字键 + A 即可输入。
     只注入小写 ASCII 字母，依赖站方的拼音搜索（实测 'huozhe' → 《活着》）。 */
  var KBD = 'wr-hh-kbd';
  var kbdTarget = null, kbdBuf = '', kbdKeys = [], kbdIdx = 0, kbdRows = [];
  function buildKbd() {
    kbdRows = [
      'qwertyuiop'.split(''),
      'asdfghjkl'.split(''),
      ['BSP', 'z', 'x', 'c', 'v', 'b', 'n', 'm', 'CLR'],
      ['SPACE', 'GO', 'CLOSE']
    ];
    /* 字典序便于用「最近邻网格」算法做二维导航 */
    kbdKeys = [];
    var r, c;
    for (r = 0; r < kbdRows.length; r++) {
      for (c = 0; c < kbdRows[r].length; c++) {
        kbdKeys.push({ k: kbdRows[r][c], r: r, c: c });
      }
    }
  }
  function kbdVisible() { return !!document.getElementById(KBD); }
  function kbdPaint() {
    var box = document.getElementById(KBD);
    if (!box) return;
    var cells = $$('#' + KBD + ' .wr-hh-kc');
    for (var i = 0; i < cells.length; i++) {
      cells[i].classList.toggle('on', i === kbdIdx);
      cells[i].setAttribute('aria-pressed', String(i === kbdIdx));
    }
    var b = $('#wr-hh-kbuf');
    if (b) b.textContent = kbdBuf || '书名 / 作者 / 拼音';
    /* 保证键盘整体可见 */
    var cur = cells[kbdIdx];
    if (cur) {
      try { cur.scrollIntoView({ block: 'nearest', inline: 'nearest' }); } catch (e) {}
    }
  }
  function setNativeValue(el, v) {
    try {
      var d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
      if (d && d.set) d.set.call(el, v); else el.value = v;
    } catch (e) { el.value = v; }
    el.dispatchEvent(new Event('input', { bubbles: true }));
  }
  function showKbd() {
    if (kbdVisible()) { kbdPaint(); return; }
    if (!kbdRows.length) buildKbd();
    var box = document.createElement('div');
    box.id = KBD;
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', '搜索');
    var html = '<div class="wr-hh-dialog-heading"><strong>搜索</strong>' +
      '<button class="wr-hh-close" aria-label="关闭搜索" title="关闭搜索">' + icon('close') + '</button></div>' +
      '<div class="wr-hh-krow wr-hh-kbufrow"><div class="wr-hh-kbuf" id="wr-hh-kbuf" aria-live="polite"></div></div>';
    for (var r = 0; r < kbdRows.length; r++) {
      html += '<div class="wr-hh-krow">';
      for (var c = 0; c < kbdRows[r].length; c++) {
        var k = kbdRows[r][c];
        var cls = 'wr-hh-kc';
        if (k.length > 1) cls += ' wr-hh-kfn';
        if (k === 'GO') cls += ' wr-hh-kgo';
        var text = { GO: '搜索', BSP: '删除', CLR: '清空', SPACE: '空格', CLOSE: '取消' }[k] || k;
        html += '<button class="' + cls + '" data-k="' + k + '">' + text + '</button>';
      }
      html += '</div>';
    }
    box.innerHTML = html;
    box.addEventListener('click', function (ev) {
      if (ev.target.closest('.wr-hh-close')) { hideKbd(); return; }
      var t = ev.target.closest('.wr-hh-kc');
      if (!t) return;
      var cells = $$('#' + KBD + ' .wr-hh-kc');
      kbdIdx = cells.indexOf(t);
      runKbd();
    });
    showOverlay();
    document.body.appendChild(box);
    if (!kbdTarget) kbdTarget = findInput();
    kbdIdx = 0; kbdPaint();
    invalidateNow();
  }
  function hideKbd(keepInput) {
    var b = document.getElementById(KBD);
    if (!b && !keepInput) return;
    if (b) b.remove();
    hideOverlay();
    if (!keepInput) {
      if (kbdTarget) { try { kbdTarget.blur(); } catch (x) {} }
      if (typing()) { try { document.activeElement.blur(); } catch (x2) {} }
      var cancel = $('.search_input_cancel');
      if (cancel) cancel.click();
      document.body.classList.remove('wr-hh-searching');
      syncNav();
      focusFirst();
    }
    invalidateNow();
  }
  function typeKey(ch) {
    kbdTarget = findInput() || kbdTarget;
    if (!kbdTarget) return false;
    /* 让站方确认焦点落在它自己的输入框上（激活 React 的受控逻辑） */
    try { if (document.activeElement !== kbdTarget) kbdTarget.focus(); } catch (e) {}
    setNativeValue(kbdTarget, kbdBuf);
    return true;
  }
  /* ⚠️⚠️ 关键旁路开关：扩展在 document【捕获阶段】监听键盘并 stopPropagation，
     这会挡住站方 React 自己的 Enter 处理（搜索提交）。
     因此扩展「主动合成的」按键必须置 SUPPRESS，让本监听器直接放行。 */
  var SUPPRESS = false;

  function submitSearch() {
    /* ⚠️ 站方搜索是 React 受控组件 + 有 debounce：
       输入后立刻发 Enter 会落空（实测：URL 不变）。必须
       ① 重新取一次输入框（React 可能已重建 DOM）
       ② 重新 focus（React 重建后焦点丢失）
       ③ 等 ≥700ms 让 debounce 归位，再发 Enter，且重试一次 */
    var t = findInput() || kbdTarget;
    if (!t) { diag({ search: 'no-input' }); return; }
    var q = kbdBuf;
    var searchPath = location.pathname + location.search;
    if (!q.trim()) { showHint('请输入书名或作者'); return; }
    setNativeValue(t, q);
    hideKbd(true);
    diag({ search: 'submitting', q: q });

    var fire = function () {
      if (location.pathname + location.search !== searchPath) return false;
      var el = findInput() || (t && t.isConnected ? t : null);
      if (!el) return false;
      try { el.focus(); } catch (e) {}
      var o = { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, cancelable: true };
      SUPPRESS = true;                    /* ⭐ 放行给站方，别被自己的捕获监听器吃掉 */
      try {
        ['keydown', 'keypress', 'keyup'].forEach(function (x) {
          el.dispatchEvent(new KeyboardEvent(x, o));
        });
      } finally { SUPPRESS = false; }
      return true;
    };

    setTimeout(function () {
      fire();
      setTimeout(function () {
        /* 若 1.2s 后仍没跳走，补一发 */
        if (location.pathname === '/' || /^\/(web\/)?$/.test(location.pathname)) fire();
        setTimeout(function () {
          if (location.pathname + location.search !== searchPath) return;
          var e2 = findInput();
          if (e2) { try { e2.blur(); } catch (x) {} }
          document.body.classList.remove('wr-hh-searching');
          syncNav();
          invalidateNow();
          if (!focusEl || !focusEl.isConnected) reanchor();
          diag({ search: 'done', path: location.pathname });
        }, 2200);
      }, 1200);
    }, 700);
  }
  function kbdMove(dir) {
    if (!kbdKeys.length) return;
    var c = kbdKeys[kbdIdx], best = -1, bs = Infinity;
    for (var i = 0; i < kbdKeys.length; i++) {
      if (i === kbdIdx) continue;
      var k = kbdKeys[i], dr = k.r - c.r, dc = k.c - c.c;
      var sc = Infinity;
      if (dir === 'up')    { if (dr >= 0) continue; sc = Math.abs(dr) * 100 + Math.abs(dc); }
      if (dir === 'down')  { if (dr <= 0) continue; sc = Math.abs(dr) * 100 + Math.abs(dc); }
      if (dir === 'left')  { if (dr !== 0 || dc >= 0) continue; sc = Math.abs(dc); }
      if (dir === 'right') { if (dr !== 0 || dc <= 0) continue; sc = Math.abs(dc); }
      if (sc < bs) { bs = sc; best = i; }
    }
    if (best < 0) return;      /* 行内到头就停住，不做跨行回绕（更可预期） */
    kbdIdx = best; kbdPaint();
  }
  function runKbd() {
    var k = kbdKeys[kbdIdx] && kbdKeys[kbdIdx].k;
    if (!k) return;
    if (k === 'BSP') {
      kbdBuf = kbdBuf.slice(0, -1);
      kbdTarget = findInput() || kbdTarget;
      if (kbdTarget) setNativeValue(kbdTarget, kbdBuf);
    } else if (k === 'CLR') {
      kbdBuf = '';
      kbdTarget = findInput() || kbdTarget;
      if (kbdTarget) setNativeValue(kbdTarget, '');
    } else if (k === 'GO') {
      submitSearch();
      return;
    } else if (k === 'CLOSE') {
      hideKbd();
      return;
    } else {
      var ch = k === 'SPACE' ? ' ' : k;
      kbdBuf += ch;
      typeKey(ch);
    }
    kbdPaint();
    diag({ kbd: kbdBuf });
  }

  /* ================= 评论划线选择 ================= */
  var annotationEl = null;
  function annotationItems() {
    var raw = $$('.wr_underline_wrapper');
    var out = [];
    var top = hasNav() ? rc(document.getElementById(NAV)).bottom : 0;
    for (var i = 0; i < raw.length; i++) {
      var e = raw[i], r = rc(e), cs = getComputedStyle(e);
      if (!e.isConnected || r.width < 8 || r.height < 4) continue;
      if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity || '1') < .05) continue;
      if (r.right <= 0 || r.bottom <= 0 || r.left >= innerWidth || r.top >= innerHeight) continue;
      if (r.top + r.height / 2 < top) continue;
      out.push(e);
    }
    out.sort(function (a, b) {
      var ar = rc(a), br = rc(b);
      return Math.abs(ar.top - br.top) > 8 ? ar.top - br.top : ar.left - br.left;
    });
    return out;
  }
  function annotationLabel(e) {
    if (!e) return '';
    var text = (e.getAttribute('data-wr-hh-annotation-label') ||
      e.getAttribute('title') || e.textContent || '').replace(/\s+/g, ' ').trim();
    if (!text || text === '划线评论') return '划线评论';
    return text || '划线评论';
  }
  function clearAnnotation() {
    var old = $$('[data-wr-hh-annotation]');
    for (var i = 0; i < old.length; i++) old[i].removeAttribute('data-wr-hh-annotation');
    var had = annotationEl;
    annotationEl = null;
    if (had) had.classList.remove('wr-hh-annotation');
  }
  function paintAnnotation(e) {
    var old = $$('.wr-hh-annotation');
    for (var i = 0; i < old.length; i++) old[i].classList.remove('wr-hh-annotation');
    annotationEl = e;
    if (!e) return;
    e.classList.add('wr-hh-annotation');
    var label = annotationLabel(e);
    e.setAttribute('data-wr-hh-annotation-label', label);
    e.setAttribute('aria-label', label + '，按 A 查看评论');
    diag({ annotation: true, text: annotationLabel(e), index: annotationItems().indexOf(e) + 1 });
  }
  function selectAnnotation(step) {
    if (!isReader() || openPanel()) return false;
    var items = annotationItems();
    if (!items.length) { clearAnnotation(); showHint('本页没有可选的划线评论'); return false; }
    var at = annotationEl ? items.indexOf(annotationEl) : -1;
    if (at < 0) at = 0;
    else at = (at + (step < 0 ? -1 : 1) + items.length) % items.length;
    paintAnnotation(items[at]);
    return true;
  }
  /* The reviews panel exposes a native close button; use it before the
     background bridge so B is independent of MV3 worker wake-up. */
  function floatPanelCloseButton() {
    var panel = openPanel();
    if (!panel) return null;
    var selectors = [
      '.reader_float_panel_header_closeBtn',
      '[class*="float_panel"] [class*="closeBtn"]',
      '[class*="float_panel"] [class*="close"]'
    ];
    for (var i = 0; i < selectors.length; i++) {
      var list = $$(selectors[i]);
      for (var j = 0; j < list.length; j++) {
        var e = list[j], r = rc(e);
        if (!e.isConnected || !shown(e) || r.width < 8 || r.height < 8) continue;
        if (!panel.contains(e) && !e.closest('[class*="float_panel"]')) continue;
        return e;
      }
    }
    return null;
  }
  function clickFloatPanelClose() {
    var button = floatPanelCloseButton();
    if (!button) return false;
    var context = beginReaderBusy('close');
    watchReaderBusy('close', context);
    try { button.click(); return true; } catch (x) { finishReaderBusy(false); }
    return false;
  }
  function openAnnotation() {
    if (!annotationEl || !annotationEl.isConnected) return false;
    annotationEl.setAttribute('data-wr-hh-annotation', '1');
    /*
     * The site installs a native click handler on the underline itself, so
     * element.click() opens the review panel without touching the MV3 worker.
     * Keep the bridge as a fallback for reader builds that only accept trusted
     * input; the retry path there also survives a cold service worker.
     */
    var context = beginReaderBusy('annotation');
    watchReaderBusy('annotation', context);
    try {
      annotationEl.click();
      return true;
    } catch (x) {
      readerInput('annotation');
      return true;
    }
  }
  /* ================= 翻页（点站内按钮） ================= */
  var pCache = {};
  /* The page turners are the most repeated lookup in the reader (Y / L1 / R1).
     The original code scanned every span,div,a,button in the document and read
     innerText on each hit, and innerText forces a rendered-text layout read per
     element.

     A match is a leaf element whose whole text is exactly the label, so the
     lookup prunes on a widened tag list and then reads textContent, which never
     forces layout. The children check has to happen before the text comparison:
     textContent on a container returns the concatenated text of every
     descendant, so without it the enclosing wrapper matches first and the click
     lands on the wrapper instead of the page turner.

     Do NOT reach for :empty here. It only matches elements with no child nodes
     at all, so a real label (which is a text node) never matches it, and
     appending it to a comma-separated list silently applies to the last branch
     only. Both were verified against real Chromium.

     The tag list stays exactly the original span,div,a,button. Widening it was
     tried and reverted: it is not a superset, it also matches elements the
     original could never find, which changes what gets clicked. */
  var PAGE_LABEL_SEL = 'span,div,a,button';
  function pageBtn(dir) {
    var want = dir === 'next' ? '下一页' : '上一页';
    if (pCache[dir] && pCache[dir].isConnected && shown(pCache[dir])) return pCache[dir];
    var els = document.querySelectorAll(PAGE_LABEL_SEL);
    for (var i = 0; i < els.length; i++) {
      var e = els[i];
      /* Only leaves can hold the label alone. This also keeps textContent from
         collecting the text of every descendant of a wrapper. */
      if (e.children.length) continue;
      if (mine(e)) continue;
      if ((e.textContent || '').trim() !== want) continue;
      if (!shown(e)) continue;
      pCache[dir] = e; return e;
    }
    return null;
  }
  function turnPage(dir) {
    var b = pageBtn(dir);
    if (b) { try { b.click(); return true; } catch (e) {} }
    return false;
  }

  /* ================= 站方入口 ================= */
  var readerBusyState = null;
  var READER_BUSY_LABELS = {
    'font-previous': '正在调整字号',
    'font-next': '正在调整字号',
    'activate': '正在应用',
    'catalog': '正在打开目录',
    'settings': '正在打开阅读设置',
    'close': '正在关闭面板',
    'annotation': '正在打开评论'
  };
  function readerFontLevel() {
    var match = document.body && document.body.className.match(/wr_reader_font_size_level_(\d+)/);
    return match ? match[1] : '';
  }
  function selectionSignature() {
    return $$('.font-panel-content-fonts-item').map(function (e) {
      var cs = getComputedStyle(e);
      return [
        e.className,
        e.getAttribute('aria-selected') || '',
        e.getAttribute('data-selected') || '',
        e.style.fontFamily || '',
        cs.fontFamily,
        cs.fontWeight
      ].join('|');
    }).join('||');
  }
  function readerTextStyleSignature() {
    var host = $('.readerChapterContent,.wr_horizontalReader') || document.body;
    if (!host) return '';
    var cs = getComputedStyle(host);
    return [host.className, cs.fontFamily, cs.fontSize, cs.fontWeight].join('|');
  }
  function busyContext(action) {
    var context = {
      kind: '',
      action: action,
      beforeFontLevel: readerFontLevel(),
      selectionSignature: '',
      textStyleSignature: '',
      beforePanel: action === 'close' ? openPanel() : null
    };
    if (action === 'activate' && focusEl && focusEl.matches &&
        focusEl.matches('.font-panel-content-fonts-item')) {
      context.kind = 'font';
      context.selectionSignature = selectionSignature();
      context.textStyleSignature = readerTextStyleSignature();
    }
    return context;
  }
  function readerBusyLabel(action, context) {
    if (action === 'activate' && context && context.kind === 'font') return '正在切换字体';
    return READER_BUSY_LABELS[action] || '正在应用';
  }
  function paintReaderBusy(action, context) {
    var el = $('#wr-hh-busy');
    if (!el) {
      el = document.createElement('div');
      el.id = 'wr-hh-busy';
      el.setAttribute('role', 'status');
      el.setAttribute('aria-live', 'polite');
      el.innerHTML = '<span class="wr-hh-spinner" aria-hidden="true"></span><strong></strong>';
      document.body.appendChild(el);
    }
    el.querySelector('strong').textContent = readerBusyLabel(action, context);
    document.body.classList.add('wr-hh-reader-busy');
    invalidateNow();
  }
  function beginReaderBusy(action) {
    if (readerBusyState) return readerBusyState.context;
    var context = busyContext(action);
    readerBusyState = {
      action: action,
      context: context,
      started: Date.now(),
      timer: null
    };
    paintReaderBusy(action, context);
    return context;
  }
  function readerBusyComplete(action, context) {
    if (action === 'font-previous' || action === 'font-next') {
      return readerFontLevel() !== context.beforeFontLevel;
    }
    if (action === 'catalog') {
      return $$('.readerCatalog').some(function (p) {
        return shown(p) && p.matches('.readerCatalog');
      });
    }
    if (action === 'settings') {
      var panel = openPanel();
      return !!(panel && shown(panel) &&
        (panel.matches('.font-panel-content') || panel.querySelector('.font-panel-content')));
    }
    if (action === 'close') return !openPanel();
    if (action === 'annotation') return !!openPanel();
    if (action === 'activate' && context.kind === 'font') {
      return selectionSignature() !== context.selectionSignature ||
        readerTextStyleSignature() !== context.textStyleSignature;
    }
    return true;
  }
  function finishReaderBusy(ok) {
    var state = readerBusyState;
    readerBusyState = null;
    if (state && state.timer) clearTimeout(state.timer);
    var el = $('#wr-hh-busy');
    if (el) el.remove();
    if (document.body) document.body.classList.remove('wr-hh-reader-busy');
    invalidateNow();
    if (!ok) showHint('操作未完成，请重试');
  }
  function watchReaderBusy(action, context) {
    var state = readerBusyState;
    if (!state || state.context !== context) return;
    /* Font activation compares computed styles across every font row, so it
       cannot be polled at the same cadence as the cheap DOM checks. A font
       swap takes a few hundred ms to settle; polling it every 50 ms only
       bought extra style recalcs, not a faster overlay. */
    var expensive = action === 'activate' && context && context.kind === 'font';
    var interval = expensive ? 160 : 50;
    function poll() {
      if (!readerBusyState || readerBusyState !== state) return;
      var elapsed = Date.now() - state.started;
      if (readerBusyComplete(action, context)) {
        if (elapsed < 200) {
          state.timer = setTimeout(poll, 200 - elapsed);
        } else {
          finishReaderBusy(true);
        }
        return;
      }
      if (elapsed >= 5000) {
        finishReaderBusy(false);
        return;
      }
      state.timer = setTimeout(poll, interval);
    }
    state.timer = setTimeout(poll, expensive ? 160 : 30);
  }
  var readerInputPending = false;
  function readerInput(action) {
    if (readerInputPending) return true;
    readerInputPending = true;
    if (!readerBusyState) {
      var initialBusyContext = beginReaderBusy(action);
      watchReaderBusy(action, initialBusyContext);
    }
    var beforeFontLevel = action === 'font-previous' || action === 'font-next'
      ? document.body.className.match(/wr_reader_font_size_level_(\d+)/) : null;
    beforeFontLevel = beforeFontLevel ? beforeFontLevel[1] : '';
    var activating = action === 'activate' ? focusEl : null;
    if (activating) activating.setAttribute('data-wr-hh-activate', '1');
    var closing = action === 'close' ? openPanel() : null;
    if (closing) closing.setAttribute('data-wr-hh-active-panel', '1');
    function finish(resultFailed, result) {
      if (closing) closing.removeAttribute('data-wr-hh-active-panel');
      if (activating) activating.removeAttribute('data-wr-hh-activate');
      if (resultFailed && beforeFontLevel) {
        var afterFontLevel = document.body.className.match(/wr_reader_font_size_level_(\d+)/);
        if (afterFontLevel && afterFontLevel[1] !== beforeFontLevel) resultFailed = false;
      }
      if (resultFailed) {
        diag({ readerInput: action, error: (result && result.error) || 'Input service rejected action' });
        readerInputPending = false;
        finishReaderBusy(false);
        return;
      }
      setTimeout(function () {
        readerInputPending = false;
        invalidateNow();
        var panel = openPanel();
        if (panel) {
          var slider = panel.querySelector('.reader_font_control_slider_track');
          if (slider) {
            slider.setAttribute('role', 'slider');
            slider.setAttribute('aria-label', '字号');
            slider.setAttribute('aria-valuemin', '1');
            slider.setAttribute('aria-valuemax', '7');
            var knob = slider.querySelector('.reader_font_control_slider_dot');
            var level = -1, distance = Infinity;
            if (knob) {
              var kr = knob.getBoundingClientRect(), center = kr.left + kr.width / 2;
              Array.from(slider.querySelectorAll('.reader_font_control_slider_track_level_dot')).forEach(function (dot, i) {
                var dr = dot.getBoundingClientRect(), d = Math.abs(dr.left + dr.width / 2 - center);
                if (d < distance) { distance = d; level = i; }
              });
            }
            slider.setAttribute('aria-valuenow', String(level + 1));
          }
          if (action === 'catalog' || action === 'settings' ||
              !focusEl || !focusEl.isConnected || !panel.contains(focusEl)) {
            focusEl = null;
            focusAt(0);
          } else focusAtEl(focusEl);
        }
      }, 100);
    }
    function send(attempt) {
      chrome.runtime.sendMessage({ type: 'reader-input', action: action }, function (result) {
        var lastError = chrome.runtime.lastError;
        var message = (lastError && lastError.message) ||
          (!result || result.ok ? '' : result.error) || '';
        if ((lastError || !result || !result.ok) && attempt < 2 &&
            /message port closed|service worker|input service unavailable|failed to fetch|networkerror/i.test(message)) {
          /* Two things make the first press land on nothing: an MV3 worker that
             was asleep, and a local bridge that is not listening yet because it
             starts before the browser and has no page target to drive. Both are
             transient, so retry rather than reporting the action as failed. */
          setTimeout(function () { send(attempt + 1); }, attempt === 0 ? 450 : 1200);
          return;
        }
        finish(!!lastError || !result || !result.ok,
          result || { error: message });
      });
    }
    send(0);
    return true;
  }
  function openCatalog() {
    pCache = {};
    return readerInput('catalog');
  }
  function openSetting() {
    pCache = {};
    return readerInput('settings');
  }

  /* ================= ⭐ 退出提示（不再自毁页面）=================
     ⚠️⚠️ 血泪：`window.close()` 在 Chrome `--app` 模式下无效（进程不退出），
       若此时再 `location.href='about:blank'` ⇒ 应用变成【白屏死页面】，
       进程还在、SSH 还在、但什么都点不动 —— 用户以为"崩了"。
     ✅ 真正的退出只有一条路：gptokeyb 的 **START + SELECT**（`-k chrome` 直接杀进程）。
        扩展 JS 无权杀进程，所以这里只做「明确提示」，绝不自毁页面。 */
  function showHint(txt) {
    var id = 'wr-hh-hint';
    var old = document.getElementById(id);
    if (old) old.remove();
    var d = document.createElement('div');
    d.id = id;
    d.setAttribute('role', 'status');
    d.textContent = txt;
    document.body.appendChild(d);
    setTimeout(function () { try { d.remove(); } catch (e) {} }, 4500);
  }
  function quitApp() {
    showHint('退出微信读书\n\n请同时按住  START + SELECT\n（按住约 1 秒）');
  }

  /* ================= 返回 ================= */
  function openPanel() {
    var sels = ['.readerCatalog', '.font-panel-content', '[class*="catalog_"]', '[class*="float_panel"]',
                '[class*="readerSetting"]', '[class*="readerNote"]', '[class*="menu_container"]'];
    for (var i = 0; i < sels.length; i++) {
      var l = $$(sels[i]);
      for (var j = 0; j < l.length; j++) {
        var el = l[j];
        /* Mine first so the hot sweep never forces a layout read for our own
           dialogs; shown() then reuses the same rect instead of reading twice. */
        if (!el.isConnected || mine(el)) continue;
        var r = rc(el);
        if (r.width < 60 || r.height < 60) continue;
        if (r.left >= innerWidth - 20 || r.right <= 20) continue;
        if (!shownSized(el, r)) continue;
        return el;
      }
    }
    return null;
  }
  function retryButton() {
    var buttons = $$('.chapterContentError .retry,.readerError button,[class*="reader"] button.retry');
    for (var i = 0; i < buttons.length; i++) if (shown(buttons[i])) return buttons[i];
    return null;
  }
  function syncRetry() {
    var retry = isReader() ? retryButton() : null;
    if (retry && !menuEl() && !kbdVisible() && !openPanel()) {
      finishLoading();
      if (focusEl !== retry) {
        clearFx(); focusEl = retry; focusKey = keyOf(retry);
        retry.classList.add(FOCUS);
        retry.setAttribute('aria-label', '重试加载章节');
      }
    } else if (focusEl && focusEl.matches('.chapterContentError .retry') && !retry) {
      clearFx(); focusEl = null; focusKey = '';
    }
    return retry;
  }
  function goBack() {
    if (document.body.classList.contains('body_search_show')) {
      var cancelSearch = $('.search_input_cancel');
      if (cancelSearch) cancelSearch.click();
      document.body.classList.remove('wr-hh-searching');
      invalidateNow();
      syncNav();
      reanchor();
      return;
    }
    /* ① 站方浮层（目录/设置/笔记/评论）打开 → 先关掉它 */
    var panel = openPanel();
    if (panel) {
      /* Reviews panels use their own close control; this also avoids the
         cold-MV3 first-message race that previously made B ineffective. */
      if (clickFloatPanelClose()) return;
      readerInput('close');
      return;
    }
    /* ② 阅读器内 → 明确回书架
       ⚠️ 不能只靠 history.back()：实测 Chrome `--app` 模式 + SPA 下
          history.length 可能为 1（或栈被 replaceState 清空）⇒ B 完全无效。
       ⚠️ 额外用 path 兜底：有些书不是 .wr_horizontalReader 布局
          （图/PDF 版），单靠 DOM 判定会漏 ⇒ 双条件任一命中即视为阅读器。 */
    if (isReader() || /^\/web\/reader\//.test(location.pathname)) {
      var origin;
      try { origin = JSON.parse(sessionStorage.getItem('wr-hh-reader-origin') || 'null'); } catch (x) {}
      if (origin && (origin.href === '/' || /^\/web\/category\/[a-z0-9_]+$/.test(origin.href))) {
        pendingOriginKey = origin.key;
        try { sessionStorage.setItem('wr-hh-discovery-return', origin.key); } catch (x) {}
        discoveryMode = origin.mode || 'suggestions';
        go(origin.href);
      } else go('/web/shelf');
      return;
    }
    if (/^\/web\/category\//.test(location.pathname)) {
      setDiscovery(/^\/web\/category\/\d+$/.test(location.pathname) ? 'categories' : 'suggestions');
      return;
    }
    if (location.pathname === '/') { go('/web/shelf'); return; }
    /* ③ 非阅读器页：优先走站内导航链接（SPA，最快），其次 history，最后硬跳 */
    var a = document.querySelector('a[href="/web/shelf"],a[href="/"]');
    if (a) { try { a.click(); return; } catch (e) {} }
    if (history.length > 1) { history.back(); return; }
    location.href = '/';
  }

  /* ================= 掌机原生菜单 ================= */
  var mIdx = 0;
  var MITEMS = [];
  function menuItems() {
    var base = [
      { t: '书架', ico: 'album', act: function () { go('/web/shelf'); } },
      { t: '发现', ico: 'star', act: function () { setDiscovery('suggestions'); } },
      { t: '退出', ico: 'close', act: quitApp }
    ];
    return isReader() ? [
      { t: '目录', ico: 'list', act: openCatalog },
      { t: '阅读设置', ico: 'setting', act: openSetting },
      { t: '上一页', ico: 'arrow', act: function () { turnPage('prev'); } },
      { t: '下一页', ico: 'article3', act: function () { turnPage('next'); } },
      base[0], base[2]
    ] : [{ t: '搜索', ico: 'search', act: openSearch }].concat(base);
  }
  function paintMenu() {
    var its = $$('#' + MENU + ' .wr-hh-mi');
    for (var i = 0; i < its.length; i++) {
      its[i].classList.toggle('on', i === mIdx);
      its[i].setAttribute('aria-pressed', String(i === mIdx));
    }
  }
  function showMenu() {
    if (menuEl()) return;
    var m = document.createElement('div');
    m.id = MENU;
    m.setAttribute('role', 'dialog');
    m.setAttribute('aria-modal', 'true');
    m.setAttribute('aria-label', isReader() ? '阅读菜单' : '书架菜单');
    MITEMS = menuItems();
    m.innerHTML = '<div class="wr-hh-dialog-heading"><strong>' +
      (isReader() ? '阅读菜单' : '书架菜单') + '</strong><button class="wr-hh-close" ' +
      'aria-label="关闭菜单" title="关闭菜单">' + icon('close') + '</button></div>' +
      '<div class="wr-hh-menu-grid">' + MITEMS.map(function (x) {
        return '<button class="wr-hh-mi">' + icon(x.ico) + '<span>' + x.t + '</span></button>';
      }).join('') + '</div>';
    m.addEventListener('click', function (ev) {
      if (ev.target.closest('.wr-hh-close')) { hideMenu(); return; }
      var t = ev.target.closest('.wr-hh-mi');
      if (!t) return;
      mIdx = $$('#' + MENU + ' .wr-hh-mi').indexOf(t);
      runMenu();
    });
    showOverlay();
    document.body.appendChild(m);
    mIdx = 0; paintMenu();
  }
  function hideMenu() { var m = menuEl(); if (m) m.remove(); hideOverlay(); }
  function runMenu() {
    var it = MITEMS[mIdx];
    hideMenu();
    if (it && it.act) setTimeout(it.act, 40);
  }

  /* ================= 导航条 ================= */
  /* ⚠️ 只用真实存在的站内章节：'/'=首页、'/web/shelf'=书架。
       自造的「我的」没有对应页面（点击无效）⇒ v7 移除，避免"点了没反应"。 */
  var TABS = [{ t: '书架', h: '/web/shelf' }, { t: '发现', h: '/' }, { t: '搜索', search: true }];
  function activateTab(tab) {
    var item = TABS[+tab.getAttribute('data-i')];
    if (!item) return;
    if (item.search) openSearch();
    else if (item.h === '/') {
      discoveryMode = 'suggestions';
      clearSuggestions();
      try { sessionStorage.setItem('wr-hh-discovery-mode', discoveryMode); } catch (x) {}
      go(item.h);
    }
    else go(item.h);
  }
  var discoveryMode = 'suggestions', pendingOriginKey = '';
  var suggestionBatch = null;
  try { discoveryMode = sessionStorage.getItem('wr-hh-discovery-mode') || 'suggestions'; } catch (x) {}
  function saveSuggestions(key) {
    var books = $$('.wr_suggestion_card_wrapper').filter(shown).slice(0, 4).map(function (e) {
      var image = $('img', e);
      var book = { href: e.href, cover: image ? image.currentSrc || image.src : '' };
      ['title', 'author', 'reason'].forEach(function (field) {
        var text = $('.wr_suggestion_card_content_' + field, e);
        book[field] = text ? text.textContent : '';
      });
      return book;
    });
    try { sessionStorage.setItem('wr-hh-suggestions', JSON.stringify({ key: key, books: books })); } catch (x) {}
  }
  function clearSuggestions() {
    suggestionBatch = null; pendingOriginKey = '';
    document.body.removeAttribute('data-wr-hh-snapshot');
    var grid = $('#wr-hh-suggestions'); if (grid) grid.remove();
    try {
      sessionStorage.removeItem('wr-hh-suggestions');
      sessionStorage.removeItem('wr-hh-discovery-return');
    } catch (x) {}
    invalidateNow();
  }
  function restoreSuggestions() {
    if (!suggestionBatch && pendingOriginKey) {
      try {
        var saved = JSON.parse(sessionStorage.getItem('wr-hh-suggestions') || 'null');
        if (saved && saved.key === pendingOriginKey && Array.isArray(saved.books) && saved.books.length === 4 &&
            saved.books.every(function (book) {
              var url = new URL(book.href, location.href);
              return url.origin === location.origin && /^\/web\/reader\/[a-z0-9]+$/.test(url.pathname);
            })) suggestionBatch = saved;
      } catch (x) {}
    }
    if (!suggestionBatch) return;
    var host = $('.wr_index_page_top_section_content_suggestions');
    if (!host) return;
    document.body.setAttribute('data-wr-hh-snapshot', '1');
    if ($('#wr-hh-suggestions')) return;
    // Mount outside the site's hydrated tree so it cannot replace the saved batch.
    var grid = document.createElement('div'); grid.id = 'wr-hh-suggestions';
    suggestionBatch.books.forEach(function (book) {
      var link = document.createElement('a'); link.className = 'wr_suggestion_card_wrapper'; link.href = book.href;
      var content = document.createElement('div'); content.className = 'wr_suggestion_card_content';
      var cover = document.createElement('div'); cover.className = 'wr_bookCover wr_suggestion_card_cover';
      var image = document.createElement('img'); image.className = 'wr_bookCover_img'; image.alt = book.title;
      if (/^https:\/\//.test(book.cover)) image.src = book.cover;
      cover.appendChild(image); content.appendChild(cover);
      var info = document.createElement('div'); info.className = 'wr_suggestion_card_content_info';
      ['title', 'author', 'reason'].forEach(function (field) {
        var text = document.createElement('div'); text.className = 'wr_suggestion_card_content_' + field;
        text.textContent = book[field] || ''; info.appendChild(text);
      });
      content.appendChild(info); link.appendChild(content); grid.appendChild(link);
    });
    document.body.appendChild(grid);
    invalidateNow();
  }
  var RANKS = [
    { t: '飙升榜', h: 'rising' }, { t: '新书榜', h: 'newbook' }, { t: '总榜', h: 'all' },
    { t: '神作榜', h: 'newrating_publish' }, { t: '热搜榜', h: 'hot_search' },
    { t: '小说榜', h: 'general_novel_rising' }, { t: '潜力榜', h: 'newrating_potential_publish' }
  ];
  var CATEGORIES = [
    ['精品小说','100000'],['历史','200000'],['文学','300000'],['艺术','400000'],
    ['人物传记','500000'],['哲学宗教','600000'],['计算机','700000'],['心理','800000'],
    ['社会文化','900000'],['个人成长','1000000'],['经济理财','1100000'],['政治军事','1200000'],
    ['童书','1300000'],['教育学习','1400000'],['科学技术','1500000'],['生活百科','1600000'],
    ['期刊杂志','1700000'],['原版书','1800000'],['医学健康','2100000'],['男生小说','1900001'],
    ['女生小说','2000001']
  ];
  var loadingState = null, loadingTimer = null, navigationId = 0;
  function beginLoading(href, text) {
    var path = new URL(href, location.href).pathname;
    loadingState = { href: path, text: text || '正在加载', started: Date.now() };
    try { sessionStorage.setItem('wr-hh-loading', JSON.stringify(loadingState)); } catch (x) {}
    paintLoading();
  }
  function paintLoading() {
    var el = $('#wr-hh-loading');
    if (!el) {
      el = document.createElement('div'); el.id = 'wr-hh-loading';
      el.setAttribute('role', 'status'); el.setAttribute('aria-live', 'polite');
      el.innerHTML = '<span class="wr-hh-spinner" aria-hidden="true"></span><strong></strong><div class="wr-hh-load-actions" hidden><button data-load="retry">重试</button><button data-load="back">返回书架</button></div>';
      el.addEventListener('click', function (ev) {
        var button = ev.target.closest('[data-load]');
        if (!button) return;
        if (button.dataset.load === 'back') { finishLoading(); go('/web/shelf'); }
        else if (loadingState && loadingState.href) {
          /* A retry must not reuse go(): the failed target can be the current
             path, and go() intentionally short-circuits same-path switches. */
          window.location.assign(loadingState.href);
        }
      });
      document.body.appendChild(el);
    }
    el.querySelector('strong').textContent = loadingState.text;
    el.querySelector('.wr-hh-load-actions').hidden = true;
    el.classList.remove('wr-hh-load-slow');
    document.body.setAttribute('aria-busy', 'true');
    invalidateNow();
  }
  function finishLoading() {
    loadingState = null;
    if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null; }
    var el = $('#wr-hh-loading'); if (el) el.remove();
    document.body.removeAttribute('aria-busy');
    try { sessionStorage.removeItem('wr-hh-loading'); } catch (x) {}
    invalidateNow();
  }
  function settleLoading() {
    if (!loadingState) return;
    var ready = false;
    if (location.pathname === loadingState.href ||
        isReader() && loadingState.href.indexOf('/web/reader/') === 0 && location.pathname.indexOf(loadingState.href) === 0) {
      if (location.pathname === '/web/shelf') {
        ready = !!$('.shelfBook,.shelfArchive');
        var empty = $('.shelf_container [class*="empty"],.shelf_container [class*="Empty"]');
        if (empty && shown(empty) && /书架|书籍|暂无|空空|没有书/.test(empty.textContent)) ready = true;
      }
      else if (location.pathname === '/') ready = discoveryMode === 'categories' ? !!$('#wr-hh-categories a') : !!$('.wr_suggestion_card_wrapper');
      else if (/^\/web\/category\//.test(location.pathname)) ready = !!$('.wr_bookList_item');
      else if (isReader()) ready = !!$('.readerChapterContent canvas') || !!$('.readerChapterContent_container canvas') || !!retryButton();
    }
    var age = Date.now() - loadingState.started;
    if (ready) {
      if (age < 180) {
        if (!loadingTimer) loadingTimer = setTimeout(function () { loadingTimer = null; settleLoading(); }, 180 - age);
        return;
      }
      finishLoading();
      if (!restoreBookFocus()) focusFirst();
    } else if (age > 12000) {
      var el = $('#wr-hh-loading');
      if (el && el.querySelector('[hidden]')) {
        el.querySelector('[hidden]').hidden = false;
        el.classList.add('wr-hh-load-slow');
        invalidateNow(); focusAtEl(el.querySelector('button'));
      }
    }
  }
  function setDiscovery(mode) {
    clearSuggestions();
    discoveryMode = mode;
    try { sessionStorage.setItem('wr-hh-discovery-mode', mode); } catch (x) {}
    if (mode === 'ranks') { go('/web/category/rising'); return; }
    if (location.pathname !== '/') { go('/'); return; }
    window.scrollTo(0, 0); syncNav(); invalidateNow();
    focusAtEl($('#' + NAV + ' [data-discovery="' + mode + '"]'));
  }
  function syncDiscovery() {
    var discovery = location.pathname === '/' || /^\/web\/category\//.test(location.pathname);
    var mode = location.pathname === '/' ? discoveryMode : /^\/web\/category\/\d+$/.test(location.pathname) ? 'categories' : 'ranks';
    if (discovery) { document.body.dataset.wrHhDiscovery = mode; primeSuggestions(); }
    else delete document.body.dataset.wrHhDiscovery;
    var sub = $('#' + NAV + ' .wr-hh-subnav');
    if (!discovery) { if (sub) sub.remove(); document.body.style.removeProperty('--hh-header'); return; }
    if (!sub) {
      sub = document.createElement('div'); sub.className = 'wr-hh-subnav';
      sub.setAttribute('role', 'tablist'); sub.setAttribute('aria-label', '发现栏目');
      sub.innerHTML = [['suggestions','猜你喜欢'],['ranks','榜单'],['categories','分类']].map(function (x) {
        return '<button role="tab" data-discovery="' + x[0] + '">' + x[1] + '</button>';
      }).join('') + '<div class="wr-hh-filters" role="tablist" aria-label="榜单"></div>';
      $('#' + NAV).appendChild(sub); invalidateNow();
    }
    $$('[data-discovery]', sub).forEach(function (e) {
      e.classList.toggle('on', e.dataset.discovery === mode);
      e.setAttribute('aria-selected', String(e.dataset.discovery === mode));
    });
    var filters = $('.wr-hh-filters', sub), id = location.pathname.split('/').pop();
    var entries = mode === 'ranks' ? RANKS : mode === 'categories' && location.pathname !== '/' ? CATEGORIES.map(function (x) { return { t: x[0], h: x[1] }; }) : [];
    var signature = entries.length ? mode : '';
    if (filters.dataset.entries !== signature) {
      filters.dataset.entries = signature;
      filters.setAttribute('aria-label', mode === 'ranks' ? '榜单' : '分类');
      filters.innerHTML = entries.map(function (x) { return '<button role="tab" data-href="/web/category/' + x.h + '">' + x.t + '</button>'; }).join('');
      invalidateNow();
    }
    filters.hidden = !entries.length;
    $$('button', filters).forEach(function (e) {
      var active = e.dataset.href === location.pathname;
      e.classList.toggle('on', active); e.setAttribute('aria-selected', String(active));
    });
    document.body.style.setProperty('--hh-header', entries.length ? '140px' : '100px');
    if (location.pathname === '/' && mode === 'categories' && !$('#wr-hh-categories')) {
      var grid = document.createElement('div'); grid.id = 'wr-hh-categories';
      grid.innerHTML = CATEGORIES.map(function (x) { return '<a href="/web/category/' + x[1] + '">' + x[0] + '</a>'; }).join('');
      grid.addEventListener('click', function (ev) {
        var link = ev.target.closest('a'); if (!link) return;
        ev.preventDefault(); go(link.getAttribute('href'));
      });
      var route = document.getElementById('wr-hh-route-view');
      var content = (route && !route.hidden && route.querySelector('.wr_index_page_content_wrapper')) || $('.wr_index_page_content_wrapper');
      if (content) content.appendChild(grid);
    }
    try { pendingOriginKey = sessionStorage.getItem('wr-hh-discovery-return') || pendingOriginKey; } catch (x) {}
    if (location.pathname === '/' && mode === 'suggestions') restoreSuggestions();
    if (pendingOriginKey && !loadingState) {
      var book = findByKey(pendingOriginKey);
      if (book) focusAtEl(book);
    }
  }
  function navWanted() { return !isReader(); }
  /* Discovery is fetched as server HTML, so its buttons have no Vue handlers.
     Reuse the SSR recommendation payload and implement the small local controls here. */
  var suggestionBooks = [], suggestionIndex = 0;
  function md5(s) {
    function add32(a, b) { return (a + b) | 0; }
    function rol(n, c) { return (n << c) | (n >>> (32 - c)); }
    function cmn(q, a, b, x, shift, t) { return add32(rol(add32(add32(a, q), add32(x, t)), shift), b); }
    function ff(a, b, c, d, x, shift, t) { return cmn((b & c) | ((~b) & d), a, b, x, shift, t); }
    function gg(a, b, c, d, x, shift, t) { return cmn((b & d) | (c & (~d)), a, b, x, shift, t); }
    function hh(a, b, c, d, x, shift, t) { return cmn(b ^ c ^ d, a, b, x, shift, t); }
    function ii(a, b, c, d, x, shift, t) { return cmn(c ^ (b | (~d)), a, b, x, shift, t); }
    function cycle(x, k) {
      var a = x[0], b = x[1], c = x[2], d = x[3];
      a = ff(a, b, c, d, k[0], 7, -680876936); d = ff(d, a, b, c, k[1], 12, -389564586); c = ff(c, d, a, b, k[2], 17, 606105819); b = ff(b, c, d, a, k[3], 22, -1044525330);
      a = ff(a, b, c, d, k[4], 7, -176418897); d = ff(d, a, b, c, k[5], 12, 1200080426); c = ff(c, d, a, b, k[6], 17, -1473231341); b = ff(b, c, d, a, k[7], 22, -45705983);
      a = ff(a, b, c, d, k[8], 7, 1770035416); d = ff(d, a, b, c, k[9], 12, -1958414417); c = ff(c, d, a, b, k[10], 17, -42063); b = ff(b, c, d, a, k[11], 22, -1990404162);
      a = ff(a, b, c, d, k[12], 7, 1804603682); d = ff(d, a, b, c, k[13], 12, -40341101); c = ff(c, d, a, b, k[14], 17, -1502002290); b = ff(b, c, d, a, k[15], 22, 1236535329);
      a = gg(a, b, c, d, k[1], 5, -165796510); d = gg(d, a, b, c, k[6], 9, -1069501632); c = gg(c, d, a, b, k[11], 14, 643717713); b = gg(b, c, d, a, k[0], 20, -373897302);
      a = gg(a, b, c, d, k[5], 5, -701558691); d = gg(d, a, b, c, k[10], 9, 38016083); c = gg(c, d, a, b, k[15], 14, -660478335); b = gg(b, c, d, a, k[4], 20, -405537848);
      a = gg(a, b, c, d, k[9], 5, 568446438); d = gg(d, a, b, c, k[14], 9, -1019803690); c = gg(c, d, a, b, k[3], 14, -187363961); b = gg(b, c, d, a, k[8], 20, 1163531501);
      a = gg(a, b, c, d, k[13], 5, -1444681467); d = gg(d, a, b, c, k[2], 9, -51403784); c = gg(c, d, a, b, k[7], 14, 1735328473); b = gg(b, c, d, a, k[12], 20, -1926607734);
      a = hh(a, b, c, d, k[5], 4, -378558); d = hh(d, a, b, c, k[8], 11, -2022574463); c = hh(c, d, a, b, k[11], 16, 1839030562); b = hh(b, c, d, a, k[14], 23, -35309556);
      a = hh(a, b, c, d, k[1], 4, -1530992060); d = hh(d, a, b, c, k[4], 11, 1272893353); c = hh(c, d, a, b, k[7], 16, -155497632); b = hh(b, c, d, a, k[10], 23, -1094730640);
      a = hh(a, b, c, d, k[13], 4, 681279174); d = hh(d, a, b, c, k[0], 11, -358537222); c = hh(c, d, a, b, k[3], 16, -722521979); b = hh(b, c, d, a, k[6], 23, 76029189);
      a = hh(a, b, c, d, k[9], 4, -640364487); d = hh(d, a, b, c, k[12], 11, -421815835); c = hh(c, d, a, b, k[15], 16, 530742520); b = hh(b, c, d, a, k[2], 23, -995338651);
      a = ii(a, b, c, d, k[0], 6, -198630844); d = ii(d, a, b, c, k[7], 10, 1126891415); c = ii(c, d, a, b, k[14], 15, -1416354905); b = ii(b, c, d, a, k[5], 21, -57434055);
      a = ii(a, b, c, d, k[12], 6, 1700485571); d = ii(d, a, b, c, k[3], 10, -1894986606); c = ii(c, d, a, b, k[10], 15, -1051523); b = ii(b, c, d, a, k[1], 21, -2054922799);
      a = ii(a, b, c, d, k[8], 6, 1873313359); d = ii(d, a, b, c, k[15], 10, -30611744); c = ii(c, d, a, b, k[6], 15, -1560198380); b = ii(b, c, d, a, k[13], 21, 1309151649);
      a = ii(a, b, c, d, k[4], 6, -145523070); d = ii(d, a, b, c, k[11], 10, -1120210379); c = ii(c, d, a, b, k[2], 15, 718787259); b = ii(b, c, d, a, k[9], 21, -343485551);
      x[0] = add32(a, x[0]); x[1] = add32(b, x[1]); x[2] = add32(c, x[2]); x[3] = add32(d, x[3]);
    }
    function block(s) { var out = [], i; for (i = 0; i < 64; i += 4) out[i >> 2] = s.charCodeAt(i) + (s.charCodeAt(i + 1) << 8) + (s.charCodeAt(i + 2) << 16) + (s.charCodeAt(i + 3) << 24); return out; }
    function word(n) { var out = '', i; for (i = 0; i < 4; i++) out += ('0' + ((n >> (i * 8)) & 255).toString(16)).slice(-2); return out; }
    var state = [1732584193, -271733879, -1732584194, 271733878], tail = [], len = s.length, i;
    for (i = 64; i <= len; i += 64) cycle(state, block(s.slice(i - 64, i)));
    s = s.slice(i - 64);
    for (i = 0; i < 16; i++) tail[i] = 0;
    for (i = 0; i < s.length; i++) tail[i >> 2] |= s.charCodeAt(i) << ((i % 4) * 8);
    tail[i >> 2] |= 128 << ((i % 4) * 8);
    if (i > 55) { cycle(state, tail); for (i = 0; i < 16; i++) tail[i] = 0; }
    tail[14] = len * 8;
    cycle(state, tail);
    return word(state[0]) + word(state[1]) + word(state[2]) + word(state[3]);
  }
  function encodeBookId(value) {
    value = String(value);
    if (/^\d*$/.test(value)) {
      var parts = [];
      for (var i = 0; i < value.length; i += 9) parts.push(parseInt(value.slice(i, i + 9), 10).toString(16));
      return ['3', parts];
    }
    var hex = '';
    for (var j = 0; j < value.length; j++) hex += value.charCodeAt(j).toString(16);
    return ['4', [hex]];
  }
  function encryptBookId(value) {
    value = String(value);
    var hash = md5(value), enc = encodeBookId(value);
    var prefix = hash.slice(0, 3) + enc[0] + '2' + hash.slice(-2);
    for (var i = 0; i < enc[1].length; i++) {
      var size = enc[1][i].length.toString(16);
      prefix += (size.length === 1 ? '0' : '') + size + enc[1][i];
      if (i < enc[1].length - 1) prefix += 'g';
    }
    if (prefix.length < 20) prefix += hash.slice(0, 20 - prefix.length);
    return prefix + md5(prefix).slice(0, 3);
  }
  function readerHref(book) {
    if (book && book.href) return book.href;
    if (book && book.deepLink) {
      var deep = /[?&]v=([^&#]+)/.exec(book.deepLink);
      if (deep) return '/web/reader/' + deep[1];
    }
    return '/web/reader/' + encryptBookId(book.bookId);
  }
  var NUXT_SCRIPT = /<script[^>]*id=["']__NUXT_DATA__["'][^>]*>([\s\S]*?)<\/script>/i;
  function decodeNuxtFlat(text) {
    var flat = JSON.parse(text || '[]'), memo = {}, active = {};
    function value(index) {
      if (typeof index !== 'number') return index;
      if (active[index]) return null;
      if (Object.prototype.hasOwnProperty.call(memo, index)) return memo[index];
      var item = flat[index];
      if (!Array.isArray(item) && (!item || typeof item !== 'object')) return (memo[index] = item);
      active[index] = true;
      if (Array.isArray(item)) {
        var kind = item[0];
        if (kind === 'ShallowReactive' || kind === 'Reactive' || kind === 'Ref') { memo[index] = value(item[1]); delete active[index]; return memo[index]; }
        if (kind === 'EmptyRef') { memo[index] = null; delete active[index]; return null; }
        if (kind === 'Set' || kind === 'Map') { memo[index] = kind === 'Set' ? [] : {}; delete active[index]; return memo[index]; }
        var list = []; memo[index] = list;
        /* A tagged array starts with its tag at item[0], so the payload begins
           at item[1]. Decoding from item[0] pushed the tag name into the list as
           a phantom first element whenever the tag was not one we know, which
           silently shifted every value by one. Skip the tag for any array
           whose head is a string. */
        var from = typeof kind === 'string' ? 1 : 0;
        for (var i = from; i < item.length; i++) list.push(value(item[i]));
        delete active[index]; return list;
      }
      var out = {}; memo[index] = out;
      for (var key in item) out[key] = value(item[key]);
      delete active[index]; return out;
    }
    return { value: value, flat: flat };
  }
  function suggestionBooksFromData(text) {
    var source = decodeNuxtFlat(text), root = source && source.value(0), entries = root && root.data;
    var books = [];
    if (entries) {
      for (var key in entries) {
        var entry = entries[key];
        if (entry && Array.isArray(entry.books) && entry.books.length) { books = entry.books.slice(); break; }
      }
    }
    return books.filter(function (book) { return book && book.bookId && book.title; }).slice(0, 40);
  }
  function extractSuggestionBooks(html) {
    var match = NUXT_SCRIPT.exec(html);
    if (!match) return [];
    try { return suggestionBooksFromData(match[1]); } catch (x) { return []; }
  }
  /* Server-rendered discovery ships the recommendations in its Nuxt payload but
     no Vue handlers, so read that payload so the local refresh control can page it. */
  function primeSuggestions() {
    if (location.pathname !== '/' || suggestionBooks.length) return;
    var node = document.getElementById('__NUXT_DATA__');
    if (!node) return;
    try {
      var books = suggestionBooksFromData(node.textContent);
      if (books.length) { suggestionBooks = books; suggestionIndex = 0; }
    } catch (x) {}
  }
  function suggestionCard(book) {
    var link = document.createElement('a'); link.className = 'wr_suggestion_card_wrapper'; link.href = readerHref(book);
    link.setAttribute('rel', 'noopener noreferrer'); link.setAttribute('target', '_self');
    var content = document.createElement('div'); content.className = 'wr_suggestion_card_content';
    var cover = document.createElement('div'); cover.className = 'wr_bookCover wr_suggestion_card_cover';
    var image = document.createElement('img'); image.className = 'wr_bookCover_img'; image.alt = book.title || '书籍封面'; image.src = book.cover || '';
    cover.appendChild(image); content.appendChild(cover);
    var info = document.createElement('div'); info.className = 'wr_suggestion_card_content_info';
    ['title', 'author', 'reason'].forEach(function (field) {
      var text = document.createElement('div'); text.className = 'wr_suggestion_card_content_' + field;
      text.textContent = book[field] || (field === 'reason' ? '大家都在读' : '');
      info.appendChild(text);
    });
    content.appendChild(info); link.appendChild(content); return link;
  }
  function renderSuggestionBatch() {
    var host = $('.wr_index_page_top_section_content_suggestions');
    if (!host || !suggestionBooks.length) return false;
    var total = Math.ceil(suggestionBooks.length / 4);
    if (suggestionIndex < 0 || suggestionIndex >= total) suggestionIndex = 0;
    var books = suggestionBooks.slice(suggestionIndex * 4, suggestionIndex * 4 + 4);
    while (host.firstChild) host.removeChild(host.firstChild);
    books.forEach(function (book) { host.appendChild(suggestionCard(book)); });
    invalidateNow(); return true;
  }
  function nextSuggestions() {
    if (!suggestionBooks.length) return false;
    /* A restored batch is rendered in a separate overlay. Clear that overlay
       before paging the underlying recommendation list, otherwise the old
       four cards keep covering the newly rendered batch. */
    clearSuggestions();
    suggestionIndex = (suggestionIndex + 1) % Math.ceil(suggestionBooks.length / 4);
    renderSuggestionBatch();
    var action = $$('.wr_index_page_top_section_content_title .wr_index_page_top_section_header_action_link').filter(function (e) { return /换一批/.test(e.textContent || ''); })[0];
    if (action) focusAtEl(action);
    return true;
  }
  /* The discovery page is server rendered, and only two pieces of it are ever
     used: the content-wrapper block that becomes the route view, and the Nuxt
     payload that feeds the local refresh control. Caching the whole document
     kept a few hundred KB of markup alive in both the JS heap and
     sessionStorage for five minutes, which is expensive on a 1 GB handheld, so
     cache just those two slices. */
  var DISCOVERY_CACHE_MS = 300000, DISCOVERY_CACHE_MAX = 262144;
  var discoveryCache = null, discoveryCacheAt = 0, discoveryFetch = null;
  function discoveryPayload(html) {
    var marker = 'class="wr_index_page_content_wrapper';
    var at = html.indexOf(marker);
    if (at < 0) return null;
    at = html.lastIndexOf('<div', at);
    var depth = 0, end = at, tag = /<\/?div\b[^>]*>/gi, match;
    tag.lastIndex = at;
    while ((match = tag.exec(html))) {
      if (match[0].charAt(1) === '/') depth--;
      else if (!/\/\s*>$/.test(match[0])) depth++;
      if (depth === 0) { end = tag.lastIndex; break; }
    }
    if (!end) return null;
    return { block: html.slice(at, end), books: extractSuggestionBooks(html) };
  }
  function getDiscoveryPayload(force) {
    var now = Date.now();
    if (!force && discoveryCache && now - discoveryCacheAt < DISCOVERY_CACHE_MS) {
      return Promise.resolve(discoveryCache);
    }
    if (discoveryFetch) return discoveryFetch;
    discoveryFetch = fetch(new URL('/', location.href).href, { credentials: 'include' })
      .then(function (response) {
        if (!response.ok) throw new Error('discovery ' + response.status);
        return response.text();
      })
      .then(function (html) {
        var payload = discoveryPayload(html);
        if (payload) {
          discoveryCache = payload;
          discoveryCacheAt = Date.now();
          try {
            /* Skip persistence when the slices are still large; the in-memory
               cache is what the same-document navigation actually reads. */
            if (payload.block.length <= DISCOVERY_CACHE_MAX) {
              sessionStorage.setItem('wr-hh-discovery-cache', JSON.stringify(payload));
              sessionStorage.setItem('wr-hh-discovery-cache-at', String(discoveryCacheAt));
            } else {
              sessionStorage.removeItem('wr-hh-discovery-cache');
              sessionStorage.removeItem('wr-hh-discovery-cache-at');
            }
          } catch (x) {}
        }
        return payload;
      })
      .then(function (payload) { discoveryFetch = null; return payload; },
            function (error) { discoveryFetch = null; throw error; });
    return discoveryFetch;
  }
  try {
    var savedDiscovery = sessionStorage.getItem('wr-hh-discovery-cache');
    var savedAt = +(sessionStorage.getItem('wr-hh-discovery-cache-at') || 0);
    if (savedDiscovery && savedAt && Date.now() - savedAt < DISCOVERY_CACHE_MS) {
      var parsedDiscovery = JSON.parse(savedDiscovery);
      if (parsedDiscovery && typeof parsedDiscovery.block === 'string' && Array.isArray(parsedDiscovery.books)) {
        discoveryCache = parsedDiscovery;
        discoveryCacheAt = savedAt;
      }
    }
  } catch (x) {}
  function routeHost() {
    var host = document.getElementById('wr-hh-route-view');
    if (!host) {
      host = document.createElement('div');
      host.id = 'wr-hh-route-view';
      host.className = 'wr-hh-route-view';
      document.body.appendChild(host);
    }
    return host;
  }
  function extractRouteView(html) {
    var parsed = new DOMParser().parseFromString(html, 'text/html');
    var view = parsed.querySelector('.app_content, .ranking_page_container, #routerView');
    if (!view) throw new Error('view content missing');
    return document.importNode(view, true);
  }
  function sameDocumentNavigate(href, requestId) {
    var target = new URL(href, location.href);
    var isHome = target.pathname === '/';
    if (!/^\/$|^\/web\/shelf$|^\/web\/category\//.test(target.pathname)) return Promise.reject(new Error('unsupported view'));
    var request = isHome ? getDiscoveryPayload(false) : fetch(target.href, { credentials: 'include', headers: { 'X-Requested-With': 'XMLHttpRequest' } }).then(function (r) { if (!r.ok) throw new Error('navigation ' + r.status); return r.text(); });
    return request.then(function (payload) {
      if (requestId !== navigationId) return false;
      var host = routeHost();
      var root = document.getElementById('__nuxt') || document.getElementById('app');
      if (isHome) {
        if (!payload) throw new Error('discovery content missing');
        while (host.firstChild) host.removeChild(host.firstChild);
        host.innerHTML = payload.block;
        suggestionBooks = payload.books; suggestionIndex = 0;
      } else {
        while (host.firstChild) host.removeChild(host.firstChild);
        host.appendChild(extractRouteView(payload));
      }
      if (root) root.hidden = true;
      host.hidden = false;
      document.body.classList.toggle('wr-hh-same-document', !isHome);
      history.pushState({ wrHhView: target.pathname }, '', target.pathname + target.search + target.hash);
      document.body.classList.remove('wr-hh-searching');
      focusEl = null; invalidateNow();
      try { syncNav(); scheduleRefresh(); } catch (x) {}
      return true;
    });
  }
  function go(href) {
    var path = new URL(href, location.href).pathname;
    if (path === location.pathname) { syncNav(); return; }
    var requestId = ++navigationId;
    beginLoading(href, href === '/web/shelf' ? '正在加载书架' : '正在加载发现');
    sameDocumentNavigate(href, requestId).then(function () {
      if (requestId === navigationId) settleLoading();
    }).catch(function () {
      if (requestId !== navigationId) return;
      finishLoading();
      window.location.assign(href);
    });
  }

  /* Capture shell-owned rank links before site handlers can start a full navigation. */
  document.addEventListener('click', function (event) {
    var target = event.target;
    var tab = target.closest && target.closest('#' + NAV + ' .wr-hh-tab');
    if (tab) {
      event.preventDefault();
      event.stopPropagation();
      if (event.stopImmediatePropagation) event.stopImmediatePropagation();
      activateTab(tab);
      return;
    }
    var section = target.closest && target.closest('#' + NAV + ' [data-discovery]');
    if (section) {
      event.preventDefault();
      event.stopPropagation();
      if (event.stopImmediatePropagation) event.stopImmediatePropagation();
      setDiscovery(section.dataset.discovery);
      return;
    }
    var refresh = target.closest && target.closest('.wr_index_page_top_section_content_title .wr_index_page_top_section_header_action_link');
    if (refresh && suggestionBooks.length > 4 && /换一批/.test(refresh.textContent || '')) {
      event.preventDefault();
      event.stopPropagation();
      if (event.stopImmediatePropagation) event.stopImmediatePropagation();
      nextSuggestions();
      return;
    }
    var clicked = target.closest && target.closest('[data-href]');
    var filter = clicked && clicked.closest('#' + NAV) ? clicked : null;
    if (!filter) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.stopImmediatePropagation) event.stopImmediatePropagation();
    focusKey = keyOf(filter);
    go(filter.dataset.href);
  }, true);
  function syncNav() {
    var has = document.getElementById(NAV);
    if (navWanted()) {
      if (!has) {
        var b = document.createElement('div');
        b.id = NAV;
        b.setAttribute('role', 'navigation');
        b.setAttribute('aria-label', '微信读书');
        b.innerHTML = '<div class="wr-hh-primary"><span class="wr-hh-brand">微信读书</span>' + TABS.map(function (x, i) {
          return '<button class="wr-hh-tab' + (x.search ? ' wr-hh-search' : '') +
            '" data-i="' + i + '" aria-label="' + x.t + '" title="' + x.t + '">' +
            (x.search ? icon('search') : x.t) + '</button>';
        }).join('') + '</div>';
        document.body.appendChild(b);
        document.body.classList.add('wr-hh-has-nav');
        invalidateNow();
      }
      var c = location.pathname === '/' || /^\/web\/category\//.test(location.pathname) ? 1 : 0;
      $$('#' + NAV + ' .wr-hh-tab').forEach(function (e, i) {
        e.classList.toggle('on', i === c && !TABS[i].search);
        if (!TABS[i].search) e.setAttribute('aria-current', i === c ? 'page' : 'false');
      });
      syncDiscovery();
    } else if (has) {
      has.remove();
      document.body.classList.remove('wr-hh-has-nav');
      invalidateNow();
    }
  }

  /* ================= 按键主逻辑 ================= */
  document.addEventListener('keydown', function (e) {
    var k = e.key;

    /* ⭐ 扩展自己合成的按键 → 直接放行给站方 React（见 SUPPRESS 说明） */
    if (SUPPRESS) return;
    if ((location.pathname === '/' || /^\/web\/category\//.test(location.pathname)) && pendingOriginKey && !loadingState &&
        /^(ArrowUp|ArrowDown|ArrowLeft|ArrowRight|PageUp|PageDown|Enter|Escape|F10|Tab| )$/.test(k)) {
      pendingOriginKey = '';
      try { sessionStorage.removeItem('wr-hh-discovery-return'); } catch (x) {}
    }

    /* 退出（SELECT → F9，最高优先级） */
    if (k === 'F9') { e.preventDefault(); e.stopPropagation(); hideKbd(); quitApp(); return; }

    if (readerBusyState &&
        /^(ArrowUp|ArrowDown|ArrowLeft|ArrowRight|PageUp|PageDown|Enter| |Escape|F10|Tab|Insert|Delete|Home|End|Backspace)$/.test(k)) {
      e.preventDefault(); e.stopPropagation(); return;
    }

    if (readerInputPending && /^(ArrowUp|ArrowDown|ArrowLeft|ArrowRight|PageUp|PageDown|Enter| |Escape|F10|Tab)$/.test(k)) {
      e.preventDefault(); e.stopPropagation(); return;
    }

    /* ⭐ v6：自绘键盘打开时，按键全部交给键盘 */
    if (kbdVisible()) {
      if (k === 'ArrowUp')    { kbdMove('up');    e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'ArrowDown')  { kbdMove('down');  e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'ArrowLeft')  { kbdMove('left');  e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'ArrowRight') { kbdMove('right'); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Enter' || k === ' ') { runKbd(); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Escape' || k === 'F10') { hideKbd(); e.preventDefault(); e.stopPropagation(); return; }
      /* 真实键盘（若有）直接透传字母，顺手也能用 */
      if (k === 'Backspace' && kbdTarget) {
        kbdBuf = kbdBuf.slice(0, -1); setNativeValue(kbdTarget, kbdBuf); kbdPaint();
        e.preventDefault(); e.stopPropagation(); return;
      }
      if (/^[a-zA-Z0-9]$/.test(k)) {
        var ch = k.toLowerCase(); kbdBuf += ch; typeKey(ch);
        var bi = -1;
        for (var z = 0; z < kbdKeys.length; z++) { if (kbdKeys[z].k === ch) { bi = z; break; } }
        if (bi >= 0) kbdIdx = bi;
        kbdPaint(); e.preventDefault(); e.stopPropagation(); return;
      }
      return;
    }

    /* 处于文本输入时，唯一允许的逃生口 = Escape（先脱离再返回） */
    if (typing()) {
      if (k === 'Escape' || k === 'F10') {
        e.preventDefault(); e.stopPropagation();
        try { document.activeElement.blur(); } catch (x) {}
        var cancel = $('.search_input_cancel');
        if (cancel) cancel.click();
        var mm = menuEl(); if (mm) hideMenu();
        focusEl = null; invalidateNow();
        return;
      }
      return;
    }

    /* 掌机菜单打开 */
    if (menuEl()) {
      var n = MITEMS.length;
      if (k === 'ArrowLeft' || k === 'ArrowUp' || k === 'PageUp') {
        var step = k === 'ArrowUp' ? (innerWidth < 520 ? 2 : 3) : 1;
        mIdx = Math.max(0, mIdx - step); paintMenu();
        e.preventDefault(); e.stopPropagation(); return;
      }
      if (k === 'ArrowRight' || k === 'ArrowDown' || k === 'PageDown') {
        var step2 = k === 'ArrowDown' ? (innerWidth < 520 ? 2 : 3) : 1;
        mIdx = Math.min(n - 1, mIdx + step2); paintMenu();
        e.preventDefault(); e.stopPropagation(); return;
      }
      if (k === 'Enter') { runMenu(); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Escape' || k === 'F10') { hideMenu(); e.preventDefault(); e.stopPropagation(); return; }
      return;
    }

    if (loadingState) {
      if (/^Arrow/.test(k)) { move(k.replace('Arrow', '').toLowerCase()); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Enter' || k === ' ') { activate(); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'PageUp' || k === 'PageDown') { move(k === 'PageUp' ? 'left' : 'right'); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Escape') { finishLoading(); goBack(); e.preventDefault(); e.stopPropagation(); return; }
    }

    /* 站方浮层打开 → 焦点导航 */
    if (openPanel()) {
      if (focusEl && focusEl.classList.contains('reader_font_control_slider_track') &&
          (k === 'ArrowLeft' || k === 'ArrowRight' || k === 'PageUp' || k === 'PageDown')) {
        readerInput(k === 'ArrowLeft' || k === 'PageUp' ? 'font-previous' : 'font-next');
        e.preventDefault(); e.stopPropagation(); return;
      }
      if (/^Arrow/.test(k)) { move(k.replace('Arrow', '').toLowerCase()); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'PageUp' || k === 'PageDown') { move(k === 'PageUp' ? 'up' : 'down'); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Enter' || k === ' ') { activate(); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Escape' || k === 'F10') { goBack(); e.preventDefault(); e.stopPropagation(); return; }
      return;
    }

    /* 阅读器内：左摇杆选择评论划线 */
    if (isReader()) {
      if (k === 'Insert' || k === 'Delete') {
        selectAnnotation(k === 'Insert' ? -1 : 1);
        e.preventDefault(); e.stopPropagation(); return;
      }
      var retry = retryButton();
      if (retry && (k === 'Enter' || k === ' ')) {
        clearFx(); focusEl = retry; retry.classList.add(FOCUS);
        readerInput('activate'); e.preventDefault(); e.stopPropagation(); return;
      }
      if (k === 'ArrowLeft' || k === 'PageUp' || k === 'Home')    { turnPage('prev'); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'ArrowRight' || k === 'PageDown' || k === 'End' || k === ' ') { turnPage('next'); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Enter') {
        if (annotationEl && annotationEl.isConnected && openAnnotation()) { e.preventDefault(); e.stopPropagation(); return; }
        activate(); e.preventDefault(); e.stopPropagation(); return;
      }
      if (k === 'F10') { showMenu(); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Tab')   { openCatalog(); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Escape') { goBack(); e.preventDefault(); e.stopPropagation(); return; }
      return;
    }

    /* 浏览模式（首页 / 书架 / 详情） */
    if (/^Arrow/.test(k)) { move(k.replace('Arrow', '').toLowerCase()); e.preventDefault(); e.stopPropagation(); return; }
    if (k === 'Enter')    { activate(); e.preventDefault(); e.stopPropagation(); return; }
    /* Scroll keys stop propagation like every other consumed key here: the
       shell handles them in the capture phase, so the site must not also see
       the keydown (space in particular activates the site's own controls). */
    if (k === ' ')        { window.scrollBy(0, innerHeight * 0.85); e.preventDefault(); e.stopPropagation(); return; }
    if (k === 'PageDown') { window.scrollBy(0,  innerHeight * 0.85); e.preventDefault(); e.stopPropagation(); return; }
    if (k === 'PageUp')   { window.scrollBy(0, -innerHeight * 0.85); e.preventDefault(); e.stopPropagation(); return; }
    if (k === 'Home')     { jumpEdge('top'); e.preventDefault(); e.stopPropagation(); return; }
    if (k === 'End')      { jumpEdge('bottom'); e.preventDefault(); e.stopPropagation(); return; }
    if (k === 'F10')      { showMenu(); e.preventDefault(); e.stopPropagation(); return; }
    if (k === 'Tab')      { openCatalog(); e.preventDefault(); e.stopPropagation(); return; }
    if (k === 'Escape')   { goBack(); e.preventDefault(); e.stopPropagation(); return; }
  }, true);

  /* Keep the release of a consumed gamepad key away from website suggestions,
     including when its keydown just closed our keyboard or menu. */
  var consumedKeys = Object.create(null);
  document.addEventListener('keydown', function (e) {
    if (!SUPPRESS && e.defaultPrevented) consumedKeys[e.key] = true;
  }, true);
  ['keypress', 'keyup'].forEach(function (type) {
    document.addEventListener(type, function (e) {
      if (SUPPRESS || !consumedKeys[e.key]) return;
      if (type === 'keyup') delete consumedKeys[e.key];
      e.preventDefault();
      e.stopPropagation();
    }, true);
  });

  /* ================= 初始化 ================= */
  function boot() {
    if (window.top !== window) return;
    loadReturnKey();
    /* Wake the MV3 service worker once per document so reader actions are hot. */
    try { chrome.runtime.sendMessage({ type: 'reader-input', action: 'wake' }, function () { void chrome.runtime.lastError; }); } catch (x) {}
    /* The site sometimes drops a free_go_proxy cookie that bounces every load to
       an unreachable Tencent gateway. It is not httpOnly, so clear it on boot. */
    try {
      if (/(^|;\s*)free_go_proxy=/.test(document.cookie)) {
        document.cookie = 'free_go_proxy=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
      }
    } catch (x) {}
    document.addEventListener('click', function (event) {
      if (event.target.closest('.wr_index_page_top_section_content_title .wr_index_page_top_section_header_action_link')) clearSuggestions();
    }, true);
    try {
      new MutationObserver(function (records) {
        /* The reader renders its first chapter in many small DOM batches. The 700 ms loading timer owns completion during this window, so shell refreshes here only add layout reads to the critical path. */
        if (isReader() && loadingState) return;
        if (records.every(function (m) { return mine(m.target) || m.target.id === 'wr-diag' || !!m.target.closest('#wr-hh-loading,#wr-hh-hint,#wr-hh-busy'); })) return;
        invalidateSoon();
        scheduleRefresh();
      })
        .observe(document.body || document.documentElement, { childList: true, subtree: true });
    } catch (e) { invalidateNow(); }

    var last = location.pathname + location.search;
    var refreshTimer = null;
    function scheduleRefresh() {
      if (refreshTimer) return;
      refreshTimer = setTimeout(function () {
        refreshTimer = null; syncNav(); settleLoading(); syncRetry();
      }, 100);
    }
    try {
      var pending = readPendingLoading();
      if (pending) { loadingState = pending; paintLoading(); setBootMaskText(pending.text); }
      else sessionStorage.removeItem('wr-hh-loading');
    } catch (x) {}
    ensureBootMask();
    document.body.classList.add('wr-hh-perf');
    primeSuggestions();
    syncNav(); scheduleRefresh();
    requestAnimationFrame(releaseBootMask);
    setInterval(function () {
      if (location.pathname + location.search !== last) {
        last = location.pathname + location.search;
        loadReturnKey();
        document.body.classList.remove('wr-hh-searching');
        focusEl = null; clearAnnotation(); invalidateNow(); clearFx(); hideMenu(); pCache = {};
        setTimeout(function () { syncNav(); }, 120);
        /* ⭐⭐ v7：换页后【轮询】直到候选元素渲染出来再锚定焦点（见 anchorFocus 说明） */
        setTimeout(anchorFocus, 900);
      }
      if (loadingState) settleLoading();
    }, 700);

    setTimeout(function () { invalidateNow(); syncNav(); }, 900);
    setTimeout(function () {
      invalidateNow(); syncNav();
      if (!restoreBookFocus()) focusFirst();
    }, 2000);
    window.addEventListener('resize', function () { invalidateNow(); syncNav(); });
    /* 焦点元素被移除时自动重锚（用身份键找回同一个逻辑条目）
       空闲时放宽到 4s，交互/路由变化后恢复 900ms，避免静止页面持续做布局扫描。 */
    var focusSweepTimer = null, lastActivityAt = Date.now();
    function focusSweep() {
      if (loadingState) return;
      /* Reader canvas owns its frame budget. Only re-anchor an open overlay
         here; the catalog can render after readerInput's initial 100 ms pass. */
      if (isReader()) {
        var readerPanel = !menuEl() && !kbdVisible() ? openPanel() : null;
        if (readerPanel && (!focusEl || !document.body.contains(focusEl) || !readerPanel.contains(focusEl))) {
          invalidateNow();
          focusAt(0);
        }
        return;
      }
      if (!menuEl() && !kbdVisible()) {
        if (syncRetry()) return;
        if (restoreBookFocus()) return;
      }
      var activePanel = !menuEl() && !kbdVisible() ? openPanel() : null;
      if (activePanel && (!focusEl || !activePanel.contains(focusEl))) {
        invalidateNow();
        focusAt(0);
        return;
      }
      if (focusEl && focusEl.isConnected && document.body.contains(focusEl)) {
        if (!focusEl.classList.contains(FOCUS)) {
          clearFx();
          focusEl.classList.add(FOCUS);
        }
        return;
      }
      if (!focusKey) { if (!focusEl) focusFirst(); return; }
      invalidateNow();
      var again = findByKey(focusKey);
      if (again) { focusEl = again; clearFx();
        try { again.classList.add(FOCUS); } catch (e) {} }
      else if (!focusEl || !focusEl.isConnected) { focusAt(0); }
    }
    function scheduleFocusSweep() {
      var idle = Date.now() - lastActivityAt > 6000;
      var delay = menuEl() || kbdVisible() || openPanel() ? 250 : (idle ? 4000 : 900);
      focusSweepTimer = setTimeout(function () {
        focusSweepTimer = null;
        focusSweep();
        scheduleFocusSweep();
      }, delay);
    }
    function markActivity() {
      lastActivityAt = Date.now();
      if (!focusSweepTimer) scheduleFocusSweep();
    }
    document.addEventListener('keydown', markActivity, true);
    document.addEventListener('pointerdown', markActivity, true);
    window.addEventListener('popstate', markActivity);
    scheduleFocusSweep();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else { boot(); }
})();
