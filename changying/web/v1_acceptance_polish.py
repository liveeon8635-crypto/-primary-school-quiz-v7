"""Final acceptance polish for V1 user-facing copy and duplicate GET reads.

This layer is deliberately presentation/read-path only. It removes internal
implementation language that leaked into the teacher UI and coalesces concurrent
identical read requests that can otherwise be emitted by independent V1
enhancement layers during a single mobile render.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_ACCEPTANCE_POLISH_MARKER = "changying_v1_acceptance_polish_v1"

_EARLY_READ_COALESCER = r'''
<script id="changying_v1_acceptance_polish_v1-read-coalescer">
(()=>{
  if(window.__cyV1ReadCoalescerInstalled)return;window.__cyV1ReadCoalescerInstalled=true;
  const nativeFetch=window.fetch.bind(window),inflight=new Map();
  const isTarget=path=>path==='/teacher/v1-roster'||path==='/teacher/v1-profiles'||path==='/teacher/v1-bootstrap'||path==='/teacher/workbench-summary'||/^\/teacher\/students\/\d+\/growth-profile$/.test(path);
  window.fetch=(input,init={})=>{
    const method=String(init?.method||(input instanceof Request?input.method:'GET')||'GET').toUpperCase();
    let url;try{url=new URL(input instanceof Request?input.url:String(input),location.origin)}catch{return nativeFetch(input,init)}
    if(method!=='GET'||url.origin!==location.origin||!isTarget(url.pathname))return nativeFetch(input,init);
    const headers=new Headers(input instanceof Request?input.headers:undefined);if(init?.headers)new Headers(init.headers).forEach((v,k)=>headers.set(k,v));
    const key=method+' '+url.pathname+url.search+' '+(headers.get('authorization')||'');
    const hit=inflight.get(key);if(hit)return hit.then(r=>r.clone());
    const request=nativeFetch(input,init);inflight.set(key,request);
    const clear=()=>setTimeout(()=>{if(inflight.get(key)===request)inflight.delete(key)},250);
    request.then(clear,()=>{if(inflight.get(key)===request)inflight.delete(key)});
    return request.then(r=>r.clone());
  };
})();
</script>
'''

_COPY_REPLACEMENTS = (
    ('<span class="tag">学生是独立实体</span>', ''),
    ('保持 V1 登录态，不再跳转旧系统。', '在当前页面查看教学信息。'),
    ('不会要求重新登录旧系统。可以关闭后继续使用 V1。', '可以关闭后稍后重试。'),
    ('在 V1 内打开 →', '打开 →'),
    ('直接读取现有教师工作台，不生成虚构数据。', '汇总当前教学中的待办与提醒。'),
    ('沿用同一 student_id 查看监护人与班级历史。', '查看当前学生的监护人关联与历史教学归属。'),
    ('真实历史摘要', '历史教学摘要'),
    ('一次读取当前可见学生的连续档案摘要，避免手机端逐个请求。', '汇总当前可见学生的历史教学与时间线记录。'),
    ('已读取 ${esc(records.length)} 名当前可见学生的连续档案摘要；历史事实仍只来自现有受保护数据。', '共 ${esc(records.length)} 名学生有可查看的连续档案摘要。'),
    ('V1 当前提供“读取事实 → 教师判断 → 衔接准备”的可用只读流程；真正改变年级、学校或教学归属仍通过受权限保护的维护流程完成。', '本页用于查看衔接依据并辅助教师判断；年级、学校和教学归属不会在此自动变更。'),
    ('当前历史事实还没有标准化的“学年/学期”字段；本轮先对真实可见记录提供学生与教学归属筛选，不伪造学年数据。', '当前历史记录尚未按学年/学期单独归档，可先按学生或教学归属筛选。'),
    ('绿色只表示“已有事实可读取”，不代表自动诊断完成。计划保存、自动分析和年级变更仍未开放。', '绿色表示已有相关记录可供参考；其余步骤仍需教师确认或补充。'),
    ('<span class="tag demo">结构占位</span>', '<button class="tag" type="button" data-cy-select-student>请选择学生</button>'),
    ('当前为 V1 展示规则，尚未作为智能诊断结论。', '掌握状态仅根据当前已有记录显示，需结合课堂表现继续判断。'),
    ('V1 预留结构，尚未启用自动分析', '结合学生已有档案逐步完成衔接判断'),
    ('未来每一步都引用同一个 student_id', '所有阶段沿用同一份学生连续档案'),
)


def patch_v1_acceptance_polish_html(html: str) -> str:
    """Polish final rendered V1 HTML without changing data or permissions."""

    if V1_ACCEPTANCE_POLISH_MARKER in html:
        return html
    for old, new in _COPY_REPLACEMENTS:
        html = html.replace(old, new)
    if "</head>" not in html:
        raise RuntimeError("V1 acceptance polish: closing head marker not found")
    html = html.replace("</head>", _EARLY_READ_COALESCER + "\n</head>", 1)
    return html.replace("</body>", f"<!-- {V1_ACCEPTANCE_POLISH_MARKER} -->\n</body>", 1)


def install_v1_acceptance_polish_patch() -> None:
    """Install acceptance polish once after all other V1 rendering layers."""

    if getattr(v1_module, "_acceptance_polish_patch_installed", False):
        return
    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_acceptance_polish_html(original())

    v1_module.v1_html = patched_v1_html
    v1_module._acceptance_polish_patch_installed = True


__all__ = [
    "V1_ACCEPTANCE_POLISH_MARKER",
    "install_v1_acceptance_polish_patch",
    "patch_v1_acceptance_polish_html",
]
