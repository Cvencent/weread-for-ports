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
     SELECT      退出应用
     START       唤出掌机菜单（目录/设置/搜索/上一页/书架/退出）
     （阅读器内按 A 也唤出同一菜单）
   ============================================================ */
(function () {
  'use strict';

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
    return /\/web\/reader\//.test(location.pathname) ||
           !!$('.wr_horizontalReader,.readerChapterContent_container');
  }
  function hasNav() { return !!document.getElementById(NAV); }
  function menuEl() { return document.getElementById(MENU); }

  function shown(e) {
    if (!e || !e.isConnected) return false;
    var r = rc(e);
    if (r.width < 18 || r.height < 14) return false;
    var cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    if (parseFloat(cs.opacity || '1') < 0.04) return false;
    return true;
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
    if (activePanel) raw = activePanel.querySelectorAll(SEL);
    else if (loadingState) raw = document.querySelectorAll('#wr-hh-loading button');
    else if (document.body.classList.contains('body_search_show')) raw = document.querySelectorAll('.search_result a,.search_result button,.search_result [role="button"]');
    else if (location.pathname === '/web/shelf') raw = document.querySelectorAll('.shelfBook,.shelfArchive');
    else if (location.pathname === '/') raw = document.querySelectorAll('.wr_suggestion_card_wrapper,.wr_index_page_top_section_content_title .wr_index_page_top_section_header_action_link,#wr-hh-categories a');
    else if (/^\/web\/category\//.test(location.pathname)) raw = document.querySelectorAll('.wr_bookList_item,.ranking_page_header button,.ranking_page_header [role="button"]');
    else raw = document.querySelectorAll(SEL);
    var list = [];
    for (var i = 0; i < raw.length; i++) {
      var e = raw[i];
      if (activePanel && !activePanel.contains(e)) continue;
      if (activePanel && e.classList.contains('font-panel-content-fonts-tab')) continue;
      if (mine(e)) continue;
      if (isTextish(e)) continue;          /* ⭐ v6：排除搜索框等文本输入 */
      if (!shown(e)) continue;
      var r = rc(e);
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

    /* 网格坐标：先算坐标，再排序；导航条行号为 -1（永远置顶） */
    var tabs = activePanel ? [] : $$('#' + NAV + ' button');
    for (var k = 0; k < tabs.length; k++) {
      if (shown(tabs[k]) && out.indexOf(tabs[k]) < 0) out.push(tabs[k]);
    }
    for (var m = 0; m < out.length; m++) {
      var rr = rc(out[m]);
      var isTab = tabs.indexOf(out[m]) >= 0;
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
    var h = e.getAttribute && e.getAttribute('href');
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
    if (location.pathname === '/' && pendingOriginKey) {
      var remembered = findByKey(pendingOriginKey);
      if (remembered) { focusAtEl(remembered); return; }
    }
    if (!focusEl || !focusEl.isConnected) focusAtEl($('#' + NAV + ' [data-discovery].on') || $('#' + NAV + ' .wr-hh-tab.on'));
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

    if (dir === 'down' || dir === 'up') {
      for (i = 0; i < t.length; i++) {
        if (t[i] === c) continue;
        r = rc(t[i]); if (r.width < 1) continue;
        var top = absTop(t[i]), col = absLeft(t[i]) + r.width / 2;
        var d = (dir === 'down') ? (top - ct) : (ct - top);
        if (d <= 2) continue;                       /* 必须真的在下方/上方 */
        var sc = d * 1000 + Math.abs(col - ccol);   /* 主序=垂直距离，次序=横向偏差 */
        if (sc < bs) { bs = sc; best = i; }
      }
    } else {
      /* ←→：先只在「与本元素纵向重叠 ≥40%」的同行元素里找 */
      var band = [];
      for (i = 0; i < t.length; i++) {
        if (t[i] === c) continue;
        r = rc(t[i]); if (r.width < 1) continue;
        var top2 = absTop(t[i]), bot2 = top2 + r.height;
        var ov = Math.min(bot2, cb) - Math.max(top2, ct);
        if (ov < Math.min(r.height, cr.height) * 0.4) continue;
        var left2 = absLeft(t[i]), col2 = left2 + r.width / 2;
        if (dir === 'right' && col2 <= ccol + 2) continue;
        if (dir === 'left'  && col2 >= ccol - 2) continue;
        band.push({ i: i, d: Math.abs(col2 - ccol) });
      }
      if (band.length) {
        band.sort(function (a, b) { return a.d - b.d; });
        best = band[0].i;
      } else {
        /* 行内到头 → 跨到相邻行的最左/最右（按行中心就近） */
        for (i = 0; i < t.length; i++) {
          if (t[i] === c) continue;
          r = rc(t[i]); if (r.width < 1) continue;
          var top3 = absTop(t[i]), col3 = absLeft(t[i]) + r.width / 2;
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

  /* ================= 翻页（点站内按钮） ================= */
  var pCache = {};
  function pageBtn(dir) {
    var want = dir === 'next' ? '下一页' : '上一页';
    if (pCache[dir] && pCache[dir].isConnected && shown(pCache[dir])) return pCache[dir];
    var els = document.querySelectorAll('span,div,a,button');
    for (var i = 0; i < els.length; i++) {
      var e = els[i];
      if (e.children.length) continue;
      if ((e.innerText || '').trim() !== want) continue;
      if (!shown(e) || mine(e)) continue;
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
  var readerInputPending = false;
  function readerInput(action) {
    if (readerInputPending) return true;
    readerInputPending = true;
    var activating = action === 'activate' ? focusEl : null;
    if (activating) activating.setAttribute('data-wr-hh-activate', '1');
    var closing = action === 'close' ? openPanel() : null;
    if (closing) closing.setAttribute('data-wr-hh-active-panel', '1');
    chrome.runtime.sendMessage({ type: 'reader-input', action: action }, function (result) {
      if (closing) closing.removeAttribute('data-wr-hh-active-panel');
      if (activating) activating.removeAttribute('data-wr-hh-activate');
      if (chrome.runtime.lastError || !result || !result.ok) {
        diag({ readerInput: action, error: chrome.runtime.lastError ?
          chrome.runtime.lastError.message : (result && result.error) || 'Input service rejected action' });
        readerInputPending = false;
        showHint('操作未完成，请重试');
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
    });
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
        var r = rc(l[j]);
        if (shown(l[j]) && r.width > 60 && r.height > 60 &&
            r.left < innerWidth - 20 && r.right > 20 && !mine(l[j])) return l[j];
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
    /* ① 站方浮层（目录/设置/笔记）打开 → 先关掉它 */
    var panel = openPanel();
    if (panel) {
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
  var loadingState = null, loadingTimer = null;
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
        else { var href = loadingState.href; beginLoading(href); location.href = href; }
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
        el.querySelector('strong').textContent = '加载时间较长';
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
    if (discovery) document.body.dataset.wrHhDiscovery = mode;
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
      var content = $('.wr_index_page_content_wrapper'); if (content) content.appendChild(grid);
    }
    try { pendingOriginKey = sessionStorage.getItem('wr-hh-discovery-return') || pendingOriginKey; } catch (x) {}
    if (location.pathname === '/' && mode === 'suggestions') restoreSuggestions();
    if (pendingOriginKey && !loadingState) {
      var book = findByKey(pendingOriginKey);
      if (book) focusAtEl(book);
    }
  }
  function navWanted() { return !isReader(); }
  function go(href) {
    if (new URL(href, location.href).pathname === location.pathname) { syncNav(); return; }
    beginLoading(href, href === '/web/shelf' ? '正在加载书架' : '正在加载发现');
    var l = $$('a[href]').filter(function (e) {
      return new URL(e.getAttribute('href'), location.href).pathname === href && !mine(e) && !e.closest('#wr-hh-categories');
    })[0];
    requestAnimationFrame(function () {
      if (l) { try { l.click(); return; } catch (e) {} }
      location.href = href;
    });
  }
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
        b.addEventListener('click', function (ev) {
          var section = ev.target.closest('[data-discovery]');
          if (section) { setDiscovery(section.dataset.discovery); return; }
          var filter = ev.target.closest('[data-href]');
          if (filter) { go(filter.dataset.href); return; }
          var t = ev.target.closest('.wr-hh-tab');
          if (!t) return;
          var tab = TABS[+t.getAttribute('data-i')];
          if (tab.search) openSearch();
          else if (+t.getAttribute('data-i') === 1) setDiscovery('suggestions');
          else go(tab.h);
        });
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
      if (k === 'Enter' || k === ' ') { runMenu(); e.preventDefault(); e.stopPropagation(); return; }
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

    /* 阅读器内 */
    if (isReader()) {
      var retry = retryButton();
      if (retry && (k === 'Enter' || k === ' ')) {
        clearFx(); focusEl = retry; retry.classList.add(FOCUS);
        readerInput('activate'); e.preventDefault(); e.stopPropagation(); return;
      }
      if (k === 'ArrowLeft' || k === 'PageUp')    { turnPage('prev'); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'ArrowRight' || k === 'PageDown' || k === ' ') { turnPage('next'); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Enter' || k === 'F10') { showMenu(); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Tab')   { openCatalog(); e.preventDefault(); e.stopPropagation(); return; }
      if (k === 'Escape') { goBack(); e.preventDefault(); e.stopPropagation(); return; }
      return;
    }

    /* 浏览模式（首页 / 书架 / 详情） */
    if (/^Arrow/.test(k)) { move(k.replace('Arrow', '').toLowerCase()); e.preventDefault(); e.stopPropagation(); return; }
    if (k === 'Enter')    { activate(); e.preventDefault(); e.stopPropagation(); return; }
    if (k === ' ')        { window.scrollBy(0, innerHeight * 0.85); e.preventDefault(); return; }
    if (k === 'PageDown') { window.scrollBy(0,  innerHeight * 0.85); e.preventDefault(); return; }
    if (k === 'PageUp')   { window.scrollBy(0, -innerHeight * 0.85); e.preventDefault(); return; }
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
    document.addEventListener('click', function (event) {
      if (event.target.closest('.wr_index_page_top_section_content_title .wr_index_page_top_section_header_action_link')) clearSuggestions();
    }, true);
    try {
      new MutationObserver(function (records) {
        if (records.every(function (m) { return mine(m.target) || m.target.id === 'wr-diag' || !!m.target.closest('#wr-hh-loading,#wr-hh-hint'); })) return;
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
      var pending = JSON.parse(sessionStorage.getItem('wr-hh-loading') || 'null');
      if (pending && Date.now() - pending.started < 20000) { loadingState = pending; paintLoading(); }
      else sessionStorage.removeItem('wr-hh-loading');
    } catch (x) {}
    syncNav(); scheduleRefresh();
    setInterval(function () {
      if (location.pathname + location.search !== last) {
        last = location.pathname + location.search;
        loadReturnKey();
        document.body.classList.remove('wr-hh-searching');
        focusEl = null; invalidateNow(); clearFx(); hideMenu(); pCache = {};
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
    /* 焦点元素被移除时自动重锚（用身份键找回同一个逻辑条目） */
    setInterval(function () {
      if (loadingState) return;
      if (isReader() && !menuEl() && !kbdVisible() && !openPanel()) { syncRetry(); return; }
      if (!menuEl() && !kbdVisible() && restoreBookFocus()) return;
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
    }, 900);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else { boot(); }
})();
