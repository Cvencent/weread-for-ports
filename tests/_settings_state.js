(()=>{
  function d(e){
    if(!e)return null;
    var r=e.getBoundingClientRect(),s=getComputedStyle(e);
    return {tag:e.tagName,cls:typeof e.className==='string'?e.className:'',text:(e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,140),value:e.getAttribute&&e.getAttribute('aria-valuenow'),rect:[r.left,r.top,r.width,r.height],display:s.display,visibility:s.visibility,opacity:s.opacity,pointer:s.pointerEvents,href:e.getAttribute&&(e.getAttribute('data-href')||e.getAttribute('href'))};
  }
  return {url:location.pathname+location.search,focus:d(document.querySelector('.wr-hh-focus')),slider:d(document.querySelector('.reader_font_control_slider_track')),fontLevel:(document.querySelector('.readerChapterContent')||{}).className||null,panel:d(document.querySelector('.font-panel-content')),tabs:Array.from(document.querySelectorAll('.font-panel-content-fonts-tab-item')).slice(0,8).map(d),menu:!!document.getElementById('wr-hh-menu'),loading:!!document.getElementById('wr-hh-loading'),diag:(document.getElementById('wr-diag')||{}).textContent||null,bodyClass:document.body.className,active:document.activeElement&&d(document.activeElement)};
})()