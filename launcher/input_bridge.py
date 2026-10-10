#!/usr/bin/env python3
"""Send a small allowlist of reader actions as actual local browser input."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import sys

sys.path.insert(0, "/storage/roms/ports/browser")
import cdp


SELECTORS = {
    "catalog": ".readerControls_item.catalog",
    "settings": ".readerControls_item.fontSizeButton",
    "activate": "[data-wr-hh-activate]",
    "close": "[data-wr-hh-active-panel]",
    "font-previous": ".reader_font_control_slider_track",
    "font-next": ".reader_font_control_slider_track",
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
        var x=(left+right)/2,y=(top+bottom)/2,hit=document.elementFromPoint(x,y);
        if(hit&&(el===hit||el.contains(hit))) return {x:x,y:y};
      }
      return null;
    })()""" % json.dumps(selector)


def click_action(action):
    target = cdp.pick_page_target()
    if not target.get("url", "").startswith("https://weread.qq.com/"):
        raise ValueError("Unexpected browser target")
    ws = cdp.WS(target["webSocketDebuggerUrl"])
    try:
        if action in ("catalog", "settings"):
            ws.call(0, "Runtime.evaluate", {"expression": "document.querySelector('.readerControls')?.setAttribute('data-wr-hh-native-input','1')"})
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
        return {"ok": True}
    finally:
        if action in ("catalog", "settings"):
            ws.call(5, "Runtime.evaluate", {"expression": "document.querySelector('.readerControls')?.removeAttribute('data-wr-hh-native-input')"})
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


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 9223), Handler).serve_forever()
