"""Exercise the real virtual-gamepad -> gptokeyb -> extension -> reader chain."""
import json
from pathlib import Path
import sys
import time

from device import command, connect, evaluate


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "playwright"
CANVAS_HAS_INK = """Array.from(document.querySelectorAll('canvas')).some(c=>{
  if(c.width<200||c.height<200) return false;
  var ctx=c.getContext('2d');if(!ctx) return false;
  var pixels=ctx.getImageData(0,0,c.width,c.height).data,different=0;
  for(var i=4;i<pixels.length;i+=16){
    if(pixels[i]!==pixels[0]||pixels[i+1]!==pixels[1]||
       pixels[i+2]!==pixels[2]||pixels[i+3]!==pixels[3]) different++;
    if(different>16) return true;
  }
  return false;
})"""


def wait_for(client, expression, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            value = evaluate(client, expression)
            if value:
                return value
        except RuntimeError:
            pass
        time.sleep(0.4)
    raise AssertionError("Timed out: " + expression)


def press(client, button):
    command(client, "python3 /storage/roms/ports/browser/vpad.py " + button)
    time.sleep(0.12)


def capture(client, name):
    OUT.mkdir(parents=True, exist_ok=True)
    command(client, "XDG_RUNTIME_DIR=/var/run/0-runtime-dir WAYLAND_DISPLAY=wayland-1 "
                    "grim /tmp/weread-ui-v8.png")
    with client.open_sftp() as sftp:
        sftp.get("/tmp/weread-ui-v8.png", str(OUT / name))


def selected(client):
    return evaluate(client, """(function(){
      var e=document.querySelector('.wr-hh-focus');
      return e ? {title:e.getAttribute('aria-label')||e.innerText,href:e.getAttribute('data-href')||e.getAttribute('href')} : null;
    })()""")


def canvas_state(client):
    return evaluate(client, """(function(){
      return Array.from(document.querySelectorAll('canvas')).filter(c=>c.width>200&&c.height>200).map(c=>{
        var text=c.toDataURL(), hash=2166136261;
        for(var i=0;i<text.length;i++) hash=Math.imul(hash^text.charCodeAt(i),16777619);
        return [c.width,c.height,hash>>>0];
      });
    })()""")


def reach_text_page(client):
    for step in range(9):
        if evaluate(client, CANVAS_HAS_INK):
            return step
        if step == 8:
            raise AssertionError("No drawn text after eight next-page inputs")
        press(client, "r1")
        time.sleep(1)


def protected_layout(client):
    return evaluate(client, """Array.from(document.querySelectorAll('.readerChapterContent,.preRenderContent')).map(e=>{
      var s=getComputedStyle(e);
      return {cls:e.className,width:s.width,padding:s.padding,fontSize:s.fontSize,
        lineHeight:s.lineHeight,letterSpacing:s.letterSpacing,textAlign:s.textAlign};
    })""")


def type_gamepad(client, word):
    for letter in word:
        for _ in range(20):
            state = evaluate(client, """(function(){
              var rows=Array.from(document.querySelectorAll('#wr-hh-kbd .wr-hh-krow')).filter(r=>r.querySelector('.wr-hh-kc'));
              var cells=rows.flatMap((row,r)=>Array.from(row.querySelectorAll('.wr-hh-kc')).map((e,c)=>({key:e.dataset.k,r:r,c:c,on:e.classList.contains('on')})));
              return cells;
            })()""")
            current = next(c for c in state if c["on"])
            target = next(c for c in state if c["key"] == letter)
            if current["key"] == letter:
                press(client, "a")
                break
            if current["r"] != target["r"]:
                press(client, "down" if current["r"] < target["r"] else "up")
            else:
                press(client, "right" if current["c"] < target["c"] else "left")
        else:
            raise AssertionError("Cannot reach keyboard key " + letter)


def main():
    client = connect()
    evidence = {}
    try:
        evaluate(client, "sessionStorage.removeItem('wr-hh-return-key');window.__e2eOldDocument=true;location.href='/web/shelf';void 0")
        wait_for(client, """!window.__e2eOldDocument && location.pathname==='/web/shelf' && document.querySelector('.shelfBook') &&
          document.querySelector('.shelfBook').getBoundingClientRect().height>80 &&
          !!document.querySelector('#wr-hh-nav .wr-hh-focus')""")
        evidence["viewport"] = evaluate(client, "[innerWidth,innerHeight]")
        assert evidence["viewport"] == [640, 480]
        capture(client, "v8-final-shelf.png")
        press(client, "down")
        initial = selected(client)
        press(client, "right")
        press(client, "left")
        assert selected(client) == initial, "Reverse grid movement changed the book"
        evidence["navigation"] = initial
        print("PASS gamepad navigation", flush=True)

        if "--skip-search" not in sys.argv:
            press(client, "start")
            wait_for(client, "!!document.getElementById('wr-hh-menu')")
            capture(client, "v8-final-menu.png")
            press(client, "a")
            wait_for(client, "!!document.getElementById('wr-hh-kbd')")
            type_gamepad(client, "huozhe")
            evidence["query"] = evaluate(client, "document.getElementById('wr-hh-kbuf').textContent")
            assert evidence["query"] == "huozhe"
            capture(client, "v8-final-search-keyboard.png")
            type_gamepad(client, ["GO"])
            wait_for(client, """document.querySelector('.search_result') &&
              document.querySelector('.search_result').innerText.length>20""")
            time.sleep(4.5)
            evidence["searchResults"] = evaluate(client, "document.querySelector('.search_result').innerText.slice(0,160)")
            assert evaluate(client, "document.querySelector('.search_input_text').value") == "huozhe"
            capture(client, "v8-final-search-results.png")
            print("PASS physical keyboard search", flush=True)
            press(client, "b")
            wait_for(client, "location.pathname==='/web/shelf' && !document.body.classList.contains('body_search_show')")
            print("PASS search results cancel", flush=True)
            (OUT / "v8-search-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        evaluate(client, "window.__e2eOldDocument=true;location.reload();void 0")
        wait_for(client, "!window.__e2eOldDocument && !!document.querySelector('#wr-hh-nav .wr-hh-focus') && !!document.querySelector('.shelfBook')")
        press(client, "down")
        book = selected(client)
        assert book and book["href"] and "/web/reader/" in book["href"]
        press(client, "a")
        wait_for(client, "location.pathname.includes('/web/reader/') && document.querySelectorAll('canvas').length>0", 40)
        time.sleep(2)
        evidence["stepsToTextPage"] = reach_text_page(client)
        before = canvas_state(client)
        assert before
        geometry = protected_layout(client)
        capture(client, "v8-final-reader.png")
        press(client, "r1")
        time.sleep(1)
        after = canvas_state(client)
        assert after != before, "R1 did not change the reader canvas"
        press(client, "l1")
        time.sleep(1)
        restored = canvas_state(client)
        assert restored != after, "L1 did not change the reader canvas"
        evidence["canvas"] = {"before": before, "next": after, "previous": restored}
        print("PASS book activation and canvas pagination", flush=True)

        press(client, "start")
        wait_for(client, "!!document.getElementById('wr-hh-menu')")
        assert protected_layout(client) == geometry, "Reading menu changed pagination layout"
        capture(client, "v8-final-reader-menu.png")
        press(client, "b")
        press(client, "x")
        wait_for(client, "!!document.querySelector('.readerCatalog .wr-hh-focus')")
        evidence["catalog"] = evaluate(client, """Array.from(document.querySelectorAll('.readerCatalog,[class*="catalog_"]'))
          .filter(e=>e.getBoundingClientRect().width>60&&e.getBoundingClientRect().left<innerWidth).map(e=>e.className)""")
        assert evidence["catalog"], "X did not open a visible catalog"
        capture(client, "v8-final-catalog.png")
        press(client, "b")
        time.sleep(0.6)
        evidence["afterCatalogCancel"] = evaluate(client, "location.pathname")
        assert "/web/reader/" in evidence["afterCatalogCancel"], "B left the reader instead of closing the catalog"
        assert evaluate(client, "document.querySelector('.readerCatalog').getBoundingClientRect().height") < 60, "B did not close the catalog"
        if evaluate(client, "location.pathname.includes('/web/reader/')"):
            press(client, "b")
        wait_for(client, "location.pathname==='/web/shelf' && !!document.querySelector('.shelfBook.wr-hh-focus')")
        evidence["returnedFocus"] = selected(client)
        assert evidence["returnedFocus"]["href"] == book["href"], "B lost the selected shelf book"
        print("PASS reader menu geometry and return selection", flush=True)
        evidence["protectedLayout"] = geometry
        (OUT / "v8-e2e-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(evidence, ensure_ascii=False, indent=2), flush=True)
    finally:
        client.close()


if __name__ == "__main__":
    main()
