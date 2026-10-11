"""Open teacher-only classroom pages (big screen, class code) in a new window without re-login.

A new browser window/tab does not share the teacher's ``sessionStorage`` (iOS Safari and
"don't remember me" logins), so the page used to ask for a login and, after logging in,
V1 sent the teacher back to the workspace instead of the page they had asked for.

The V1 click handler below stages the existing one-time auth handoff (``POST /v1/auth-handoff``)
before opening the window; the target page consumes it (``POST /v1/auth-handoff/consume``,
HttpOnly cookie, single use) and keeps the token in its own ``sessionStorage``. Nothing about
the authentication code itself changes.
"""

from __future__ import annotations

OPEN_WINDOW_MARKER = "changying_open_window_handoff_v1"

# Runs inside the V1 shell: any ``<a data-cy-open-window>`` opens in a new window after staging the handoff.
OPEN_WINDOW_JS = r"""
(function(){
  if(window.__cyOpenWindowBound)return;window.__cyOpenWindowBound=true;
  function remembered(){try{return localStorage.getItem('v717Remember')==='1'}catch(e){return false}}
  function read(store,key){try{return store.getItem(key)||''}catch(e){return ''}}
  function token(){
    var rem=remembered(),v='',first=rem?[localStorage,sessionStorage]:[sessionStorage,localStorage];
    for(var i=0;i<first.length&&!v;i++){v=read(first[i],'v717Token')}
    if(!v)v=read(sessionStorage,'v6Token')||read(localStorage,'v6Token');
    return v&&v!=='demo'?v:'';
  }
  document.addEventListener('click',function(e){
    var a=e.target&&e.target.closest?e.target.closest('a[data-cy-open-window]'):null;
    if(!a)return;
    e.preventDefault();e.stopPropagation();
    var href=a.getAttribute('href');
    // Open synchronously so iOS keeps the user gesture, then point it at the page once staged.
    var w=window.open('about:blank','_blank');
    try{if(w)w.opener=null}catch(err){}
    function go(){if(w){w.location.href=href}else{location.href=href}}
    var t=token();
    if(!t){go();return}
    fetch('/v1/auth-handoff',{method:'POST',headers:{Authorization:'Bearer '+t},cache:'no-store',credentials:'same-origin'}).then(go,go);
  },true);
})();
"""

# Shared by the data-free teacher pages: stored token first, otherwise consume the staged handoff once.
PAGE_AUTH_JS = r"""
  function remembered(){try{return localStorage.getItem('v717Remember')==='1'}catch(e){return false}}
  function read(store,key){try{return store.getItem(key)||''}catch(e){return ''}}
  function storedToken(){
    var rem=remembered(),v='',first=rem?[localStorage,sessionStorage]:[sessionStorage,localStorage];
    for(var i=0;i<first.length&&!v;i++){v=read(first[i],'v717Token')}
    if(!v)v=sessionStorage.getItem('v6Token')||localStorage.getItem('v6Token')||'';
    return v&&v!=='demo'?v:'';
  }
  var triedHandoff=false;
  function obtainToken(){
    var t=storedToken();
    if(t)return Promise.resolve(t);
    if(triedHandoff)return Promise.resolve('');
    triedHandoff=true;
    return fetch('/v1/auth-handoff/consume',{method:'POST',cache:'no-store',credentials:'same-origin'})
      .then(function(r){return r.ok?r.json():null})
      .then(function(d){
        if(!d||!d.token)return '';
        try{
          sessionStorage.setItem('v717Token',d.token);
          sessionStorage.setItem('v717User',JSON.stringify({id:d.userID,name:d.name||'',role:d.role,grade:d.grade==null?null:d.grade,mustChangePassword:!!d.mustChangePassword,subscription:d.subscription||null}));
        }catch(e){}
        return d.token;
      })
      .catch(function(){return ''});
  }
"""


def with_open_window_script(html: str) -> str:
    """Append the V1 click handler once (idempotent)."""
    if OPEN_WINDOW_MARKER in html:
        return html
    snippet = f"<!-- {OPEN_WINDOW_MARKER} --><script>{OPEN_WINDOW_JS}</script>"
    return html.replace("</body>", snippet + "</body>", 1) if "</body>" in html else html + snippet


__all__ = ["OPEN_WINDOW_JS", "OPEN_WINDOW_MARKER", "PAGE_AUTH_JS", "with_open_window_script"]
