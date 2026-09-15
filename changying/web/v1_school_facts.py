"""Keep V1 school mode honest about the data that actually exists.

The current production model has teaching classes, students, assignments and
teacher workbench facts, but it does not yet persist a normalized school
calendar/timetable or a separate school data domain.  V1 therefore must not
present a synthetic timetable or imply that such a domain already exists.

This patch is presentation-only.  It reuses the existing authenticated read
APIs and turns ``今日课表`` into a factual teaching overview until a real
schedule model is introduced.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_SCHOOL_FACTS_MARKER = "changying_v1_school_facts_v1"

_SCHOOL_DESC_OLD = "按学校 → 学年 → 学期 → 年级 → 班级 → 学科组织教学。"
_SCHOOL_DESC_NEW = "学校模式按当前账号可见班级与学生组织；学年、学期和学校独立数据域尚未标准化落表。"
_SCHOOL_CARD_OLD = "学校数据域内的教学入口"
_SCHOOL_CARD_NEW = "复用当前账号已有教学数据，不虚构独立学校数据域"
_SHOW_FEATURE_MARKER = "  async function showFeature(name){\n"

_SCHOOL_TODAY_FUNCTION = r'''  async function showSchoolToday(){
    openShell('今日课表');
    try{
      const [rows,workbench]=await Promise.all([
        classesAndStudents(''),
        readJson('/teacher/workbench-summary').catch(()=>({summary:{},classes:[]}))
      ]);
      const s=workbench.summary||{};
      setFeature(`<div class="cy-feature-note"><b>当前没有标准化课表时段数据。</b><br>以下只展示当前账号今天可核对的真实教学事实：可见班级、学生数量和教师待办。不会生成虚构的上课时间、教室或学科安排。</div><div class="cy-op-grid" style="margin-top:12px"><div class="cy-op-stat"><b>${esc(rows.length)}</b><span>可见教学归属</span></div><div class="cy-op-stat"><b>${esc(rows.reduce((n,x)=>n+(x.students?.length||0),0))}</b><span>关系记录数</span></div><div class="cy-op-stat"><b>${esc(s.overdue||0)}</b><span>已逾期</span></div><div class="cy-op-stat"><b>${esc(s.openTodos||0)}</b><span>班级待办</span></div></div><div class="cy-op-list">${rows.slice(0,12).map(x=>`<div class="cy-op-row"><span><b>${esc(x.class?.name||'教学归属')}</b><small>当前可见学生 ${esc(x.students?.length||0)} 人</small></span><small>真实关系</small></div>`).join('')||'<div class="empty">当前没有可见教学归属</div>'}</div><p class="cy-op-muted" style="margin-top:12px">待后续真正建立学校、学年、学期、课节与时间段数据模型后，这里才能升级为严格意义上的“今日课表”。</p>`);
    }catch(err){featureError(err)}
  }
'''


def patch_v1_school_facts(html: str) -> str:
    """Patch school-mode copy and the timetable card without inventing data."""

    if V1_SCHOOL_FACTS_MARKER in html:
        return html

    if _SCHOOL_DESC_OLD not in html:
        raise RuntimeError("V1 school facts patch: school description marker not found")
    html = html.replace(_SCHOOL_DESC_OLD, _SCHOOL_DESC_NEW, 1)

    if _SCHOOL_CARD_OLD not in html:
        raise RuntimeError("V1 school facts patch: school card marker not found")
    html = html.replace(_SCHOOL_CARD_OLD, _SCHOOL_CARD_NEW, 1)

    if _SHOW_FEATURE_MARKER not in html:
        raise RuntimeError("V1 school facts patch: operational feature marker not found")
    html = html.replace(_SHOW_FEATURE_MARKER, _SCHOOL_TODAY_FUNCTION + _SHOW_FEATURE_MARKER, 1)

    feature_start = "  async function showFeature(name){\n    const f=(name||'').trim();\n"
    feature_new = feature_start + "    if(f==='今日课表'){await showSchoolToday();return}\n"
    if feature_start not in html:
        raise RuntimeError("V1 school facts patch: showFeature body marker not found")
    html = html.replace(feature_start, feature_new, 1)

    return html.replace("</body>", f"<!-- {V1_SCHOOL_FACTS_MARKER} --></body>", 1)


def install_v1_school_facts_patch() -> None:
    """Install the school-mode presentation boundary once before routes bind."""

    if getattr(v1_module, "_school_facts_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_school_facts(original())

    v1_module.v1_html = patched_v1_html
    v1_module._school_facts_patch_installed = True


__all__ = [
    "V1_SCHOOL_FACTS_MARKER",
    "install_v1_school_facts_patch",
    "patch_v1_school_facts",
]
