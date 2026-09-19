"""Expose teacher-confirmed rubric details in the mature grading UI."""

from __future__ import annotations

from types import ModuleType


RUBRIC_REVIEW_UI_MARKER = "changying_rubric_review_ui_v1"

RUBRIC_REVIEW_UI_SNIPPET = r'''
<style id="changying_rubric_review_ui_v1-style">
.cy-rubric-review{margin-top:14px;padding:12px;border:1px solid #dce5f0;border-radius:14px;background:#f8fbff}
.cy-rubric-review>h3{margin:0 0 8px;font-size:15px}
.cy-rubric-row{margin-top:9px;padding:11px;border:1px solid #e5e9f1;border-radius:12px;background:#fff}
.cy-rubric-row-head{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;flex-wrap:wrap}
.cy-rubric-points{display:grid;gap:5px;margin-top:8px;font-size:12px;line-height:1.55}
.cy-rubric-met{color:#137a52}.cy-rubric-missed{color:#b54747}.cy-rubric-review-needed{color:#9a6700}
</style>
<script id="changying_rubric_review_ui_v1-script">
(function(){
  if(window.__cyRubricReviewUIInstalled)return;
  window.__cyRubricReviewUIInstalled=true;

  function safe(value){
    return String(value==null?'':value).replace(/[&<>"']/g,function(ch){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch];
    });
  }
  function items(value){return Array.isArray(value)?value.filter(Boolean):[]}
  function rubricRows(result){
    var rows=items(result&&result.rubric_results);
    if(!rows.length)return '';
    return '<div class="cy-rubric-review"><h3>评分要点核对</h3>'+
      '<div class="muted">以下为 AI 按教师已审核评分点给出的辅助核对；最终分数仍由教师确认。</div>'+
      rows.map(function(row,index){
        var ratio=row.suggested_ratio;
        var ratioText=(typeof ratio==='number'&&isFinite(ratio))
          ?Math.round(Math.max(0,Math.min(1,ratio))*100)+'%'
          :'需教师判断';
        var met=items(row.met_points);
        var missed=items(row.missed_points);
        var review=items(row.needs_teacher_review);
        return '<div class="cy-rubric-row">'+
          '<div class="cy-rubric-row-head"><b>'+(index+1)+'. '+safe(row.knowledge||('题目 #'+(row.question_id||'')))+'</b>'+
          '<span class="badge">'+safe('AI建议完成度 '+ratioText)+'</span></div>'+
          '<div class="cy-rubric-points">'+
          (met.length?'<div class="cy-rubric-met"><b>✓ 已达到：</b>'+met.map(safe).join('；')+'</div>':'')+
          (missed.length?'<div class="cy-rubric-missed"><b>△ 未达到：</b>'+missed.map(safe).join('；')+'</div>':'')+
          (review.length?'<div class="cy-rubric-review-needed"><b>需教师确认：</b>'+review.map(safe).join('；')+'</div>':'')+
          (!met.length&&!missed.length&&!review.length?'<div class="muted">AI 未形成可靠的逐点评估，请教师直接核对原作答。</div>':'')+
          '</div></div>';
      }).join('')+
      '</div>';
  }

  var base=window.aiIssueRows;
  if(typeof base!=='function')return;
  window.aiIssueRows=function(result){
    return base(result)+rubricRows(result);
  };
})();
</script>
'''


def inject_rubric_review_ui(html: str) -> str:
    if RUBRIC_REVIEW_UI_MARKER in html:
        return html
    marker = RUBRIC_REVIEW_UI_SNIPPET + f"\n<!-- {RUBRIC_REVIEW_UI_MARKER} -->"
    if "</body>" in html:
        return html.replace("</body>", marker + "\n</body>", 1)
    return html + marker


def install_rubric_review_ui(implementation: ModuleType) -> None:
    if getattr(implementation, "_rubric_review_ui_installed", False):
        return
    implementation.INDEX_HTML = inject_rubric_review_ui(implementation.INDEX_HTML)
    implementation._rubric_review_ui_installed = True


__all__ = [
    "RUBRIC_REVIEW_UI_MARKER",
    "inject_rubric_review_ui",
    "install_rubric_review_ui",
]
