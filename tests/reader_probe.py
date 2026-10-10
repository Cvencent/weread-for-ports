"""Exercise error recovery with a real failed chapter and real gamepad input."""
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from device import connect, evaluate
from e2e import OUT, capture, press, wait_for, canvas_state, CANVAS_HAS_INK, reach_text_page

client = connect()
try:
    evaluate(client, "window.__readerOldDocument=true;location.href='/web/reader/33332bf05cbba0333b1efb4';void 0")
    wait_for(client, "!window.__readerOldDocument && !!document.querySelector('canvas') && !!document.querySelector('.readerControls')", 40)
    time.sleep(2)
    steps = reach_text_page(client)
    sidebar = evaluate(client, """(function(){var e=document.querySelector('.readerControls'),s=getComputedStyle(e);
      return {opacity:s.opacity,pointerEvents:s.pointerEvents,rect:e.getBoundingClientRect().toJSON()};})()""")
    assert sidebar['opacity'] == '0' and sidebar['pointerEvents'] == 'none', sidebar
    capture(client, 'v9-reader.png')
    subprocess.run([sys.executable, str(Path(__file__).with_name('probe.py')), 'error', 'after'], check=True)
    wait_for(client, "!!document.querySelector('.chapterContentError .retry.wr-hh-focus')")
    capture(client, 'v9-retry.png')
    before = evaluate(client, "document.querySelector('.chapterContentError').innerText")
    press(client, 'a')
    wait_for(client, "!document.querySelector('.chapterContentError .retry') && !!document.querySelector('.readerChapterContent canvas')", 40)
    wait_for(client, CANVAS_HAS_INK, 40)
    assert not evaluate(client, "!!document.querySelector('#wr-hh-menu')"), 'A opened the menu during a chapter error'
    capture(client, 'v9-retry-recovered.png')
    press(client, 'a')
    wait_for(client, "!!document.querySelector('#wr-hh-menu')")
    press(client, 'b')
    press(client, 'x')
    wait_for(client, "!!document.querySelector('.readerCatalog .wr-hh-focus')")
    assert evaluate(client, "getComputedStyle(document.querySelector('.readerControls')).pointerEvents==='none'")
    press(client, 'b')
    wait_for(client, "document.querySelector('.readerCatalog').getBoundingClientRect().height<60")
    evidence = {'sidebar':sidebar,'realFailure':before,'gamepadRetryRecovered':True,
                'menuRestoredAfterRecovery':True,'hiddenToolbarCatalog':True,
                'stepsToTextPage':steps,'drawnTextAfterRetry':True,'canvas':canvas_state(client)}
    (OUT / 'v9-reader-evidence.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PASS hidden toolbar, actual failed chapter, gamepad A retry, menu and X catalog')
finally:
    client.close()
