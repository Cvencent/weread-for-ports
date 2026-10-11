#!/usr/bin/env python3
"""Send a small allowlist of reader actions as actual local browser input."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys

# cdp.py ships next to this file and is also copied into the browser directory
# that the launcher uses; accept either location so a partial update still works.
#
# Load it by path rather than by pushing a directory onto sys.path. Putting it
# back afterwards leaves the interpreter exactly as it was, and the plain
# `import cdp` fallback keeps working when the module is already on the path.
import importlib.util as _importlib_util


def _load_cdp():
    for _candidate in ("/storage/roms/ports/browser",
                       os.path.dirname(os.path.abspath(__file__))):
        _path = os.path.join(_candidate, "cdp.py")
        if not os.path.isfile(_path):
            continue
        _spec = _importlib_util.spec_from_file_location("cdp", _path)
        if _spec is None or _spec.loader is None:
            continue
        _module = _importlib_util.module_from_spec(_spec)
        _sys_modules = sys.modules.get("cdp")
        _spec.loader.exec_module(_module)
        sys.modules["cdp"] = _module
        return _module
    import cdp as _module          # already importable: use it as-is
    return _module


cdp = _load_cdp()


SELECTORS = {
    "catalog": ".readerControls_item.catalog",
    "settings": ".readerControls_item.fontSizeButton",
    "activate": "[data-wr-hh-activate]",
    "close": "[data-wr-hh-active-panel]",
    "font-previous": ".reader_font_control_slider_track",
    "font-next": ".reader_font_control_slider_track",
    "annotation": "[data-wr-hh-annotation]",
}


def point_expression(selector):
    return """(function(){
      var list=Array.from(document.querySelectorAll(%s));
      for(var el of list){
        var r=el.getBoundingClientRect(),s=getComputedStyle(el);
        if(r.width<10||r.height<10||s.display==='none'||s.visibility==='hidden') continue;
        var left=Math.max(0,r.left),right=Math.min(innerWidth,r.right);
        var top=Math.max(0,r.top),bottom=Math.min(innerHeight,r.bottom);
        if(right-left<8||bottom-top<8) continue;
        var points=[[(left+right)/2,(top+bottom)/2],[left+4,(top+bottom)/2],[right-4,(top+bottom)/2],[(left+right)/2,top+4],[(left+right)/2,bottom-4]];
        for(var p=0;p<points.length;p++){
          var x=points[p][0],y=points[p][1],hit=document.elementFromPoint(x,y);
          if(hit&&(el===hit||el.contains(hit)||hit.contains(el))) return {x:x,y:y};
        }
      }
      return null;
    })()""" % json.dumps(selector)


# The data- prefix is part of the attribute name: the stylesheet matches it as
# [data-wr-hh-native-input-holders], so setAttribute must use the same name.
NATIVE_INPUT_MARK = "data-wr-hh-native-input-holders"


# The expressions are kept as plain strings so the tests can run the exact
# shipped JavaScript in a real browser instead of a paraphrase of it.
HOLD_NATIVE_INPUT = """(function(){
  var root=document.querySelector('.readerControls');
  if(!root) return 0;
  var n=parseInt(root.getAttribute(%(mark)s)||'0',10)+1;
  root.setAttribute(%(mark)s,String(n));
  return n;
})()""" % {"mark": json.dumps(NATIVE_INPUT_MARK)}

RELEASE_NATIVE_INPUT = """(function(){
  var root=document.querySelector('.readerControls');
  if(!root) return 0;
  var n=parseInt(root.getAttribute(%(mark)s)||'0',10)-1;
  if(n>0){root.setAttribute(%(mark)s,String(n));return n;}
  root.removeAttribute(%(mark)s);
  return 0;
})()""" % {"mark": json.dumps(NATIVE_INPUT_MARK)}


def _hold_native_input_source():
    """The exact JavaScript the bridge sends to take a reference."""
    return HOLD_NATIVE_INPUT


def _release_native_input_source():
    """The exact JavaScript the bridge sends to drop a reference."""
    return RELEASE_NATIVE_INPUT


def _hold_native_input(ws, mid):
    """Take a reference on the attribute that makes the site toolbar clickable.

    The server is threaded, so several actions can be in flight at once and
    they all share one document attribute. A plain set/remove pair is only safe
    by luck of timing: clear it while another action sits between mousePressed
    and mouseReleased and that click is dispatched against a toolbar with
    pointer-events disabled, which is the "X does nothing" symptom this
    attribute exists to prevent. Count the holders instead, and only clear the
    attribute once the last one lets go.
    """
    ws.call(mid, "Runtime.evaluate", {"expression": HOLD_NATIVE_INPUT})


def _release_native_input(ws, mid):
    ws.call(mid, "Runtime.evaluate", {"expression": RELEASE_NATIVE_INPUT})


def click_action(action):
    target = cdp.pick_page_target()
    if not target.get("url", "").startswith("https://weread.qq.com/"):
        raise ValueError("Unexpected browser target")
    ws = cdp.WS(target["webSocketDebuggerUrl"])
    try:
        if action in ("catalog", "settings"):
            _hold_native_input(ws, 0)
        expression = point_expression(SELECTORS[action])
        if action in ("font-previous", "font-next"):
            expression = """(function(){
              var track=document.querySelector('.reader_font_control_slider_track');
              if(!track||track.getBoundingClientRect().height<10) return null;
              var dots=Array.from(track.querySelectorAll('.reader_font_control_slider_track_level_dot'));
              var knob=track.querySelector('.reader_font_control_slider_dot');
              if(!knob) return null;
              var kr=knob.getBoundingClientRect(),center=kr.left+kr.width/2;
              var current=-1,distance=Infinity;
              dots.forEach((e,i)=>{var r=e.getBoundingClientRect(),d=Math.abs(r.left+r.width/2-center);
                if(d<distance){distance=d;current=i;}});
              if(current<0) return null;
              var next=Math.max(0,Math.min(dots.length-1,current+(%d)));
              var r=dots[next].getBoundingClientRect(),t=track.getBoundingClientRect();
              var x=r.left+r.width/2,y=t.top+t.height/2,hit=document.elementFromPoint(x,y);
              return hit&&track.contains(hit)?{x:x,y:y}:null;
            })()""" % (1 if action == "font-next" else -1)
        if action == "close":
            expression = """(function(){
              var panel=document.querySelector('[data-wr-hh-active-panel]');
              if(!panel||panel.getBoundingClientRect().height<60) return null;
              for(var point of [[8,8],[8,innerHeight-8],[innerWidth-8,8]]){
                var hit=document.elementFromPoint(point[0],point[1]);
                if(hit&&!panel.contains(hit)&&!hit.closest('button,a,input,[role="button"]'))
                  return {x:point[0],y:point[1]};
              }
              return null;
            })()"""
        response = ws.call(1, "Runtime.evaluate", {
            "expression": expression, "returnByValue": True,
        })
        point = response.get("result", {}).get("result", {}).get("value")
        if not point:
            raise ValueError("Reader control is hidden or obstructed")
        for index, event in enumerate(("mousePressed", "mouseReleased"), 2):
            result = ws.call(index, "Input.dispatchMouseEvent", {
                "type": event, "x": point["x"], "y": point["y"],
                "button": "left", "clickCount": 1,
            })
            if "error" in result:
                raise ValueError("Browser rejected input")
        if action in ("font-previous", "font-next"):
            key = "ArrowLeft" if action == "font-previous" else "ArrowRight"
            code = 37 if key == "ArrowLeft" else 39
            for index, event in enumerate(("keyDown", "keyUp"), 4):
                result = ws.call(index, "Input.dispatchKeyEvent", {
                    "type": event, "key": key, "code": key,
                    "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code,
                })
                if "error" in result:
                    raise ValueError("Browser rejected keyboard input")
        return {"ok": True}
    finally:
        # Cleanup must never raise: a failure here would mask the real error and
        # leave .readerControls stuck in its pointer-events-enabled state, which
        # would make the invisible toolbar swallow the next tap.
        if action in ("catalog", "settings"):
            try:
                _release_native_input(ws, 5)
            except (OSError, ValueError, KeyError, RuntimeError):
                pass
        ws.close()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        status, result = 400, {"ok": False}
        try:
            if self.path != "/action" or self.headers.get("X-Weread-Input") != "v8":
                raise ValueError("Invalid request")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 128:
                raise ValueError("Invalid request size")
            action = json.loads(self.rfile.read(length)).get("action")
            if action not in SELECTORS:
                raise ValueError("Invalid action")
            result = click_action(action)
            status = 200
        except (OSError, ValueError, KeyError, RuntimeError):
            pass
        body = json.dumps(result).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    # Threaded: a slow CDP round trip (slow network, busy renderer) must not
    # block the extension's retry, which uses a 4 s budget of its own.
    Server(("127.0.0.1", 9223), Handler).serve_forever()
