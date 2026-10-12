import sys, time
sys.path.insert(0,'tests')
from device import connect,evaluate,protocol,command
c=connect()
def press(key,vk):
    for t in ('keyDown','keyUp'):
        protocol(c,'Input.dispatchKeyEvent',{'type':t,'key':key,'code':key,'windowsVirtualKeyCode':vk,'nativeVirtualKeyCode':vk})
try:
    print('before',evaluate(c,"({mark:document.querySelectorAll('.wr-hh-annotation').length,url:location.pathname})"))
    press('Enter',13); time.sleep(2)
    print('after',evaluate(c,"({mark:document.querySelectorAll('.wr-hh-annotation').length,data:document.querySelectorAll('[data-wr-hh-annotation]').length,diag:document.getElementById('wr-diag')&&document.getElementById('wr-diag').textContent,vis:Array.from(document.querySelectorAll('.reader_float_panel_container')).filter(function(e){var r=e.getBoundingClientRect();return r.width>60&&r.height>60}).length})"))
    print(command(c,"tail -30 /storage/roms/ports/browser/input-bridge.log"))
finally:c.close()
