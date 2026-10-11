"""Probe the actual reader settings through gamepad input."""
import json
import time

from device import command, connect, evaluate
from e2e import OUT, capture, press, protected_layout, wait_for


client = connect()
try:
    evaluate(client, "sessionStorage.removeItem('wr-hh-return-key');location.href='/web/shelf';void 0")
    wait_for(client, "!!document.querySelector('.shelfBook') && !!document.querySelector('#wr-hh-nav .wr-hh-focus')")
    press(client, "down")
    press(client, "a")
    wait_for(client, "!!document.querySelector('.readerControls_item.fontSizeButton') && !!document.getElementById('wr-diag')", 40)
    time.sleep(2)
    press(client, "start")
    wait_for(client, "!!document.getElementById('wr-hh-menu')")
    press(client, "right")
    assert evaluate(client, "document.querySelector('#wr-hh-menu .on').innerText").strip() == "阅读设置"
    press(client, "a")
    wait_for(client, """(function(){var p=document.querySelector('.font-panel-content');
      return p&&p.getBoundingClientRect().height>60;})()""")
    print("PASS settings opened", flush=True)
    result = evaluate(client, """Array.from(document.querySelectorAll('[class*="font"],[class*="Font"]'))
      .filter(e=>{var r=e.getBoundingClientRect();return r.width>60&&r.height>60&&
        r.left<innerWidth&&r.right>0&&/panel/i.test(e.className);})
      .slice(0,10).map(e=>({cls:e.className,text:e.innerText.slice(0,180),
        rect:e.getBoundingClientRect().toJSON(),
        buttons:Array.from(e.querySelectorAll('button,[role="button"]')).slice(0,12).map(b=>b.outerHTML.slice(0,240))}))""")
    assert result, "Reading settings did not open"
    bounds = evaluate(client, """(function(){var r=document.querySelector('.font-panel-content').getBoundingClientRect();
      return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight;})()""")
    assert bounds, "Settings panel exceeds the actual screen"
    wait_for(client, "document.querySelector('.reader_font_control_slider_track.wr-hh-focus')")
    font_state = "document.body.className.match(/wr_reader_font_size_level_(\\d+)/)[1]"
    original = evaluate(client, font_state)
    layout = protected_layout(client)
    press(client, "right")
    wait_for(client, f"{font_state}!=={json.dumps(original)}")
    first = evaluate(client, font_state)
    print("PASS first size adjustment", flush=True)
    press(client, "right")
    wait_for(client, f"{font_state}!=={json.dumps(first)}")
    time.sleep(1)
    changed = protected_layout(client)
    assert changed != layout, "Changing the font slider did not reach the reader"
    press(client, "left")
    wait_for(client, f"{font_state}==={json.dumps(first)}")
    press(client, "left")
    wait_for(client, f"{font_state}==={json.dumps(original)}")
    print("PASS repeated size changes and restore", flush=True)
    capture(client, "v9-final-settings.png")
    press(client, "down")
    wait_for(client, "!!document.querySelector('.font-panel-content-fonts-tab-item.wr-hh-focus')")
    press(client, "right")
    tab = evaluate(client, "document.querySelector('.font-panel-content-fonts-tab-item.wr-hh-focus').innerText")
    press(client, "a")
    wait_for(client, "!!document.querySelector('.font-panel-content-fonts-tab-item.selected.wr-hh-focus')")
    assert evaluate(client, "document.querySelector('.font-panel-content-fonts-tab-item.wr-hh-focus').innerText") == tab
    for _ in range(4):
        if "全部" in evaluate(client, "document.querySelector('.wr-hh-focus').innerText"):
            break
        press(client, "left")
    press(client, "a")
    wait_for(client, "document.querySelector('.font-panel-content-fonts-tab-item.selected').innerText.includes('全部')")
    command(client, "python3 /storage/roms/ports/browser/vpad.py " + " ".join(["down"] * 8))
    scrolling = evaluate(client, """(function(){
      var panel=document.querySelector('.font-panel-content'),focus=document.querySelector('.wr-hh-focus');
      var r=focus.getBoundingClientRect(),p=panel.getBoundingClientRect();
      var hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
      return {scroll:panel.scrollTop,title:focus.getAttribute('aria-label')||focus.innerText,
        visible:r.top>=p.top-1&&r.bottom<=p.bottom+1&&!!hit&&(hit===focus||focus.contains(hit))};
    })()""")
    assert scrolling["scroll"] > 0 and scrolling["visible"], scrolling
    capture(client, "v9-final-settings-scrolled.png")
    print("PASS font category activation preserves focus and list scrolls", flush=True)
    for _ in range(8):
        press(client, "up")
        assert evaluate(client, """(function(){
          var e=document.querySelector('.wr-hh-focus'),r=e.getBoundingClientRect();
          var hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);
          return !!hit&&(hit===e||e.contains(hit));
        })()"""), "Font list focus is hidden by the sticky settings header"
    press(client, "b")
    wait_for(client, """(function(){var p=document.querySelector('.font-panel-content');
      return !p||p.getBoundingClientRect().height<60;})()""")
    assert "/web/reader/" in evaluate(client, "location.pathname")
    press(client, "b")
    wait_for(client, "location.pathname==='/web/shelf' && !!document.querySelector('.shelfBook.wr-hh-focus')")
    (OUT / "v9-settings-evidence.json").write_text(json.dumps({
        "panel": result[0]["rect"], "fontOriginal": original, "fontFirstStep": first,
        "fontRestored": True, "categoryActivated": tab, "scrolling": scrolling,
        "returnedToShelf": True,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print("PASS settings bounds, gamepad font adjustment, cancel and return", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
finally:
    client.close()