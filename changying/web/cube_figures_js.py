"""小正方体组合体图示：浏览器端绘制（ES5）、页面注入和保存校验.

The same drawing (``cyCubeShapes``) feeds two outputs: an SVG string for the classic and V1 question views (they
build HTML strings) and SVG nodes for pages that only use DOM calls (knowledge map, diagnosis). Projection constants
match ``changying.services.cube_figures`` so the hidden-cube check on the server sees what the pupil sees.
"""
from __future__ import annotations

from typing import Any

from changying.services import cube_figures as cf
from changying.services import visual_questions as vq

CUBE_FIGURES_MARKER = "changying_cube_figures_v1"

CUBES_JS = r"""
function cyCubeShapes(fig){
  var out=[],W=0,H=0,DEPTH=__DEPTH__;
  function solid(h,s,ox,oy){
    var rows=h.length,cols=h[0].length,top=0,r,c,z;
    for(r=0;r<rows;r++)for(c=0;c<cols;c++)top=Math.max(top,h[r][c]);
    var dx=DEPTH*s,dy=DEPTH*s,base=oy+top*s+rows*dy;
    for(r=0;r<rows;r++){var d=rows-1-r;for(c=0;c<cols;c++)for(z=0;z<h[r][c];z++){
      var x=ox+c*s+d*dx,y=base-(z+1)*s-d*dy;
      out.push({t:'polygon',a:{points:[x,y,x+s,y,x+s,y+s,x,y+s].join(','),fill:'#ffffff',stroke:'#1f2937','stroke-width':1.2}});
      out.push({t:'polygon',a:{points:[x,y,x+dx,y-dy,x+s+dx,y-dy,x+s,y].join(','),fill:'#e5e7eb',stroke:'#1f2937','stroke-width':1.2}});
      out.push({t:'polygon',a:{points:[x+s,y,x+s+dx,y-dy,x+s+dx,y+s-dy,x+s,y+s].join(','),fill:'#cbd5e1',stroke:'#1f2937','stroke-width':1.2}});
    }}
    return {w:cols*s+rows*dx,h:top*s+rows*dy};
  }
  function size(h,s){var top=0;h.forEach(function(r){r.forEach(function(v){top=Math.max(top,v)})});return {w:h[0].length*s+h.length*DEPTH*s,h:top*s+h.length*DEPTH*s}}
  function grid(v,cell,ox,oy){
    v.forEach(function(row,i){row.forEach(function(on,j){
      if(on)out.push({t:'rect',a:{x:ox+j*cell,y:oy+i*cell,width:cell,height:cell,fill:'#bfdbfe',stroke:'#1e3a8a','stroke-width':1.2}});
    })});
    return {w:v[0].length*cell,h:v.length*cell};
  }
  var y=0;
  if(fig.title){out.push({t:'text',a:{x:4,y:16,'font-size':14,fill:'#111827'},s:fig.title});y=24}
  if(fig.solid){var sz=size(fig.solid,30);solid(fig.solid,30,8,y+4);W=Math.max(W,sz.w+16);y+=sz.h+16}
  // Given pictures (图①、前面…) on their own row, the A—D options on the next.
  var panels=fig.panels||[],PW=118,PH=104,per=4,slots=[],col=0,row=0;
  panels.forEach(function(p,i){
    var isOpt=/^[A-D]$/.test(p.label||'');
    if(i>0&&(col>=per||(isOpt&&!/^[A-D]$/.test(panels[i-1].label||''))))
      {col=0;row++}
    slots.push([col,row]);col++;
  });
  panels.forEach(function(p,i){
    var px=slots[i][0]*PW,py=y+slots[i][1]*(PH+22);
    out.push({t:'rect',a:{x:px+2,y:py+2,width:PW-8,height:PH,rx:8,fill:'#f8fafc',stroke:'#e5e7eb'}});
    if(p.view){var cell=Math.min(18,(PW-24)/p.view[0].length,(PH-20)/p.view.length),gw=p.view[0].length*cell,gh=p.view.length*cell;
      grid(p.view,cell,px+2+(PW-8-gw)/2,py+2+(PH-gh)/2)}
    else if(p.solid){var s=16,k=size(p.solid,s);s=Math.min(16,s*Math.min((PW-20)/k.w,(PH-16)/k.h));k=size(p.solid,s);
      solid(p.solid,s,px+2+(PW-8-k.w)/2,py+2+(PH-k.h)/2)}
    out.push({t:'text',a:{x:px+2+(PW-8)/2,y:py+PH+18,'text-anchor':'middle','font-size':14,'font-weight':700,fill:'#111827'},s:p.label||''});
    W=Math.max(W,px+PW);
  });
  if(panels.length)y+=(row+1)*(PH+22);
  return {w:Math.ceil(W),h:Math.ceil(y+4),items:out};
}
function cyGridShapes(fig){
  var out=[],W=fig.width,H=fig.height;
  var TONE={a:{fill:'#bfdbfe',stroke:'#1e3a8a',dash:''},b:{fill:'#fecaca',stroke:'#b91c1c',dash:''},ghost:{fill:'none',stroke:'#94a3b8',dash:'4 3'}};
  function draw(f,c,ox,oy){
    var i,X=function(x){return ox+x*c},Y=function(y){return oy+(H-y)*c},plain=f.hideGrid||fig.hideGrid;
    if(plain){
      // A plain drawing is cropped to the shape and its measurements, with room for the labels around it.
      var xs=[],ys=[],M=46;
      (f.shapes||[]).forEach(function(s){s.points.forEach(function(p){xs.push(p[0]);ys.push(p[1])})});
      (f.marks||[]).forEach(function(m){xs.push(m.from[0],m.to[0]);ys.push(m.from[1],m.to[1])});
      var minx=Math.min.apply(null,xs),maxx=Math.max.apply(null,xs),miny=Math.min.apply(null,ys),maxy=Math.max.apply(null,ys);
      X=function(x){return ox+M+(x-minx)*c};Y=function(y){return oy+M+(maxy-y)*c};
    }
    if(!plain){
      for(i=0;i<=W;i++)out.push({t:'line',a:{x1:X(i),y1:Y(0),x2:X(i),y2:Y(H),stroke:'#e2e8f0','stroke-width':1}});
      for(i=0;i<=H;i++)out.push({t:'line',a:{x1:X(0),y1:Y(i),x2:X(W),y2:Y(i),stroke:'#e2e8f0','stroke-width':1}});
    }
    (f.shapes||[]).forEach(function(s){var t=TONE[s.tone]||TONE.a,a={points:s.points.map(function(p){return X(p[0])+','+Y(p[1])}).join(' '),fill:t.fill,stroke:t.stroke,'stroke-width':c>14?2:1.5};
      if(t.dash)a['stroke-dasharray']=t.dash;out.push({t:'polygon',a:a});
      if(s.label){var sx=0,sy=0;s.points.forEach(function(p){sx+=p[0];sy+=p[1]});
        out.push({t:'text',a:{x:X(sx/s.points.length),y:Y(sy/s.points.length)+5,'text-anchor':'middle','font-size':Math.max(11,c*0.6),'font-weight':700,fill:t.stroke},s:s.label})}});
    if(f.axis){out.push({t:'line',a:{x1:X(f.axis[0][0]),y1:Y(f.axis[0][1]),x2:X(f.axis[1][0]),y2:Y(f.axis[1][1]),stroke:'#dc2626','stroke-width':2,'stroke-dasharray':'6 4'}});
      out.push({t:'text',a:{x:X(f.axis[1][0])+4,y:Y(f.axis[1][1])+12,'font-size':Math.max(11,c*0.6),fill:'#dc2626','font-style':'italic'},s:'l'})}
    // Measurements: 底/边 as a dimension line set off from the shape, 高 as a dashed line with a right angle at its foot.
    (f.marks||[]).forEach(function(m){
      var ax=X(m.from[0]),ay=Y(m.from[1]),bx=X(m.to[0]),by=Y(m.to[1]),fs=Math.max(12,c*0.55),
          len=Math.sqrt((bx-ax)*(bx-ax)+(by-ay)*(by-ay))||1,nx=(by-ay)/len,ny=-(bx-ax)/len,cx=0,cy=0,k=0;
      (f.shapes||[]).forEach(function(s){s.points.forEach(function(p){cx+=X(p[0]);cy+=Y(p[1]);k++})});
      if(k){cx/=k;cy/=k}
      var mx=(ax+bx)/2,my=(ay+by)/2;if((mx-cx)*nx+(my-cy)*ny<0){nx=-nx;ny=-ny}
      if(m.style==='height'){
        out.push({t:'line',a:{x1:ax,y1:ay,x2:bx,y2:by,stroke:'#475569','stroke-width':1.5,'stroke-dasharray':'5 4'}});
        var q=Math.min(10,c*0.4),sx=bx+(ax>=cx?-q:q);
        out.push({t:'polyline',a:{points:[sx,by,sx,by-q,bx,by-q].join(','),fill:'none',stroke:'#475569','stroke-width':1.2}});
        out.push({t:'text',a:{x:mx+(ax>=cx?-6:6),y:my+4,'text-anchor':ax>=cx?'end':'start','font-size':fs,fill:'#0f172a'},s:m.text});
      }else{
        var off=c*0.45,px=nx*off,py=ny*off;
        out.push({t:'line',a:{x1:ax+px,y1:ay+py,x2:bx+px,y2:by+py,stroke:'#64748b','stroke-width':1.2}});
        out.push({t:'line',a:{x1:ax+px*0.5,y1:ay+py*0.5,x2:ax+px*1.5,y2:ay+py*1.5,stroke:'#64748b','stroke-width':1.2}});
        out.push({t:'line',a:{x1:bx+px*0.5,y1:by+py*0.5,x2:bx+px*1.5,y2:by+py*1.5,stroke:'#64748b','stroke-width':1.2}});
        // Upright or slanted lines: the label sits beside the line (anchored on its outer side), not across it.
        if(Math.abs(nx)>0.6)out.push({t:'text',a:{x:mx+nx*(off+6),y:my+ny*(off+6)+fs*0.35,'text-anchor':nx<0?'end':'start','font-size':fs,fill:'#0f172a'},s:m.text});
        else out.push({t:'text',a:{x:mx+nx*(off+fs*0.9),y:my+ny*(off+fs*0.9)+fs*0.35,'text-anchor':'middle','font-size':fs,fill:'#0f172a'},s:m.text});
      }
    });
    if(f.center){out.push({t:'circle',a:{cx:X(f.center[0]),cy:Y(f.center[1]),r:c>14?4:3,fill:'#111827'}});
      out.push({t:'text',a:{x:X(f.center[0])-(c>14?12:8),y:Y(f.center[1])+(c>14?16:11),'font-size':Math.max(11,c*0.6),'font-weight':700,fill:'#111827'},s:'O'})}
    return plain?{w:(maxx-minx)*c+2*M,h:(maxy-miny)*c+2*M}:{w:W*c,h:H*c};
  }
  var y=0,MW=0;
  if(fig.title){out.push({t:'text',a:{x:4,y:16,'font-size':14,fill:'#111827'},s:fig.title});y=24}
  if(fig.shapes&&fig.shapes.length){var m=draw(fig,26,8,y+4);MW=m.w+20;y+=m.h+16}
  var panels=fig.panels||[],c=Math.min(13,104/W),PW=W*c+16,PH=H*c+8;
  panels.forEach(function(p,i){var col=i%2,row=Math.floor(i/2),px=col*(PW+12),py=y+row*(PH+26);
    out.push({t:'rect',a:{x:px+2,y:py,width:PW,height:PH,rx:8,fill:'#f8fafc',stroke:'#e5e7eb'}});
    draw(p,c,px+10,py+4);
    out.push({t:'text',a:{x:px+2+PW/2,y:py+PH+18,'text-anchor':'middle','font-size':14,'font-weight':700,fill:'#111827'},s:p.label||''});
    MW=Math.max(MW,px+PW+4)});
  if(panels.length)y+=Math.ceil(panels.length/2)*(PH+26);
  return {w:Math.ceil(MW),h:Math.ceil(y+4),items:out};
}
function cyFigureShapes(fig){return String(fig.type||'').toLowerCase()==='gridshape'?cyGridShapes(fig):cyCubeShapes(fig)}
function cyIsDrawnFigure(fig){var t=String((fig&&fig.type)||'').toLowerCase();return t==='cubes'||t==='gridshape'}
function cyCubeEsc(v){return String(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function cyCubeSvgString(fig){
  var g=cyFigureShapes(fig),body=g.items.map(function(it){
    var attrs=Object.keys(it.a).map(function(k){return k+'="'+cyCubeEsc(it.a[k])+'"'}).join(' ');
    return it.t==='text'?'<text '+attrs+'>'+cyCubeEsc(it.s)+'</text>':'<'+it.t+' '+attrs+'/>';
  }).join('');
  return '<div class="question-figure" style="margin:10px 0"><svg viewBox="0 0 '+g.w+' '+g.h+'" width="100%" style="max-width:'+Math.min(480,g.w*1.15)+'px;display:block" role="img" aria-label="题目图形">'+body+'</svg></div>';
}
function cyCubeSvgNode(fig){
  var g=cyFigureShapes(fig),NS='http://www.w3.org/2000/svg',svg=document.createElementNS(NS,'svg');
  svg.setAttribute('viewBox','0 0 '+g.w+' '+g.h);svg.setAttribute('width','100%');svg.setAttribute('role','img');svg.setAttribute('aria-label','题目图形');
  svg.setAttribute('style','max-width:'+Math.min(480,g.w*1.15)+'px;display:block;margin:10px 0');
  g.items.forEach(function(it){var n=document.createElementNS(NS,it.t);Object.keys(it.a).forEach(function(k){n.setAttribute(k,it.a[k])});if(it.t==='text')n.textContent=it.s;svg.appendChild(n)});
  return svg;
}
""".replace("__DEPTH__", repr(cf.DEPTH))

# Classic and V1 question views build HTML strings with their own figure functions; wrap them for cubes figures.
_WRAP = r"""
(function(){
  function wrap(name){var orig=window[name];if(typeof orig!=='function'||orig.__cyCubes)return;
    var w=function(fig){if(cyIsDrawnFigure(fig)){try{return cyCubeSvgString(fig)}catch(e){return ''}}return orig.apply(this,arguments)};
    w.__cyCubes=true;window[name]=w;}
  wrap('renderQuestionFigure');
})();
"""


def patch_cube_figures(html: str) -> str:
    if CUBE_FIGURES_MARKER in html or "</body>" not in html:
        return html
    snippet = f'<script id="{CUBE_FIGURES_MARKER}">{CUBES_JS}{_WRAP}</script>'
    return html.replace("</body>", snippet + "</body>", 1)


def install_cube_figure_storage(implementation: Any) -> None:
    """Let questions keep system-drawn figures (cubes, grid moves): the legacy whitelist drops unknown types."""
    if getattr(implementation, "_cube_figures_installed", False):
        return
    original = implementation._sanitize_figure

    def sanitize_figure(value: Any) -> dict[str, Any]:
        if isinstance(value, dict) and str(value.get("type") or "").strip().lower() in vq.FIGURE_TYPES:
            return vq.sanitize(value)
        return original(value)

    implementation._sanitize_figure = sanitize_figure
    implementation._cube_figures_installed = True


_V1_FIGURE_FN = "function v1RenderQuestionFigure(fig){"


def patch_v1_cube_figures(html: str) -> str:
    """V1's figure function lives inside an IIFE, so it cannot be wrapped from outside: hand cubes figures over at
    its first line instead."""
    if _V1_FIGURE_FN in html and "cyCubeSvgString(fig)" not in html:
        html = html.replace(_V1_FIGURE_FN, _V1_FIGURE_FN + "if(window.cyIsDrawnFigure&&window.cyIsDrawnFigure(fig))"
                            "return window.cyCubeSvgString(fig);", 1)
    return patch_cube_figures(html)


def install_v1_cube_figures() -> None:
    from changying.web import v1 as v1_module
    if getattr(v1_module, "_cube_figures_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched() -> str:
        return patch_v1_cube_figures(original())

    v1_module.v1_html = patched
    v1_module._cube_figures_patch_installed = True


__all__ = ["CUBES_JS", "CUBE_FIGURES_MARKER", "install_cube_figure_storage", "install_v1_cube_figures", "patch_cube_figures",
           "patch_v1_cube_figures"]
