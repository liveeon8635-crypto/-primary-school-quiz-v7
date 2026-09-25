"""Add a first-visit V1 guide and keep the same product guide permanently reachable.

The guide is presentation-only. It stores only a local browser acknowledgement and
never mutates school, student, teaching, billing, or authorization data.
"""

from __future__ import annotations

from changying.web import v1 as v1_module


V1_PRODUCT_GUIDE_MARKER = "changying_v1_product_guide_v1"
GUIDE_PATH = "/v1/guide"


def patch_v1_product_guide(html: str) -> str:
    if V1_PRODUCT_GUIDE_MARKER in html:
        return html

    top_marker = '<span class="identity-chip" id="identityChip">检查登录状态</span><button class="btn" id="identityButton" hidden>切换身份</button>'
    top_replacement = '<span class="identity-chip" id="identityChip">检查登录状态</span><button class="btn" id="guideButton" hidden>使用指南</button><button class="btn" id="identityButton" hidden>切换身份</button>'
    if top_marker not in html:
        raise RuntimeError("V1 product guide: top action marker not found")
    html = html.replace(top_marker, top_replacement, 1)

    key_marker = "const TOKEN_KEY='v717Token', USER_KEY='v717User', REMEMBER_KEY='v717Remember', IDENTITY_KEY='cyV1Identity', CYCLE_KEY='cyV1Cycle';"
    key_replacement = key_marker + "\n    const GUIDE_KEY='cyV1ProductGuideSeenV1';"
    if key_marker not in html:
        raise RuntimeError("V1 product guide: storage key marker not found")
    html = html.replace(key_marker, key_replacement, 1)

    refs_marker = "const screen=document.getElementById('screen'), chip=document.getElementById('identityChip'), identityButton=document.getElementById('identityButton');"
    refs_replacement = "const screen=document.getElementById('screen'), chip=document.getElementById('identityChip'), guideButton=document.getElementById('guideButton'), identityButton=document.getElementById('identityButton');"
    if refs_marker not in html:
        raise RuntimeError("V1 product guide: element refs marker not found")
    html = html.replace(refs_marker, refs_replacement, 1)

    login_marker = "function loginView(message=''){identityButton.hidden=true;chip.textContent='尚未登录';"
    login_replacement = "function loginView(message=''){identityButton.hidden=true;guideButton.hidden=true;chip.textContent='尚未登录';"
    if login_marker not in html:
        raise RuntimeError("V1 product guide: login marker not found")
    html = html.replace(login_marker, login_replacement, 1)

    choose_marker = "function chooseIdentity(){const choices=identitiesFor(session);"
    choose_replacement = "function chooseIdentity(){guideButton.hidden=true;const choices=identitiesFor(session);"
    if choose_marker not in html:
        raise RuntimeError("V1 product guide: identity marker not found")
    html = html.replace(choose_marker, choose_replacement, 1)

    render_marker = "    async function render(){if(!token){loginView();return}"
    guide_function = r'''    function productGuidePage(){
      const params=new URLSearchParams(location.search),first=params.get('first')==='1';
      const rawReturn=params.get('return')||'',safeReturn=rawReturn.startsWith('/v1')&&!rawReturn.startsWith('/v1/guide')?rawReturn:(session?.role==='parent'||session?.role==='student'?'/v1/student':'/v1/workspace');
      const steps=[
        ['1','学生主档案','先找到学生本人。成绩、作业、课堂表现、家长关联和历史变化都围绕同一个学生 ID 累积。','/v1/student'],
        ['2','教学归属','确认学生当前所在班级、教师和教学阶段；调班或换老师时保留历史，不重新建学生。','/v1/student'],
        ['3','课堂与学习动态','从当前教学进入课堂、练习、作业、测验和后续跟进，结果继续回到学生连续档案。','/v1/workspace'],
        ['4','家长关联','家长关系属于学生档案的一部分；需要查看家庭关联时，从学生档案进入对应信息。','/v1/student'],
        ['5','升年级衔接','升年级或升学时继续使用原学生档案，记录上一阶段事实、衔接计划和下一阶段进展。','/v1/transition'],
        ['6','历史查询','已经结束的班级、学期和课程进入往期教学；历史记录只读保留，仍能回到同一学生。','/v1/history']
      ];
      const cards=steps.map(x=>'<article class="card"><div style="display:flex;gap:12px;align-items:flex-start"><span class="tag">STEP '+x[0]+'</span><div style="min-width:0;flex:1"><h2 style="margin:0 0 8px">'+x[1]+'</h2><p style="margin:0;color:var(--muted);line-height:1.7">'+x[2]+'</p><button class="btn" data-guide-target="'+x[3]+'" style="margin-top:12px">打开这个入口</button></div></div></article>').join('');
      const title=first?'欢迎使用长缨辅学':'长缨辅学使用指南';
      const desc=first?'先用两分钟看清楚“学生连续档案 → 教学过程 → 阶段衔接 → 历史查询”的主线。以后可随时从顶部“使用指南”回来查看。':'这份说明与首次引导使用同一套内容，后续产品调整时只维护一处。';
      const content=heading(title,desc,'<span class="tag">'+(first?'首次使用':'产品说明')+'</span>')+
        '<section class="card"><h2>先记住一件事</h2><p style="line-height:1.8">长缨不是按一次作业或一个班级拆散学生记录，而是先确定学生，再把教学归属、课堂与学习动态、家庭关联、升年级衔接和历史事实持续挂在同一份档案上。</p></section>'+
        '<section class="section grid cols-2">'+cards+'</section>'+
        '<section class="section card"><div class="section-head"><div><h2>常用入口</h2><p>不知道从哪里开始时，先回到当前教学；需要完整功能时进入全部功能。</p></div></div><div style="display:flex;gap:10px;flex-wrap:wrap"><button class="btn primary" id="guideContinue">'+(first?'开始使用':'返回工作台')+'</button>'+(first?'<button class="btn" id="guideSkip">暂时跳过</button>':'')+'<a class="btn" href="/v1/tool">全部功能</a></div></section>';
      screen.innerHTML=shell(content,'guide');bindNav();
      document.querySelectorAll('[data-guide-target]').forEach(btn=>btn.onclick=()=>{localStorage.setItem(GUIDE_KEY,'1');navigate(btn.dataset.guideTarget)});
      const complete=()=>{localStorage.setItem(GUIDE_KEY,'1');navigate(safeReturn)};
      document.getElementById('guideContinue').onclick=complete;
      const skip=document.getElementById('guideSkip');if(skip)skip.onclick=complete;
    }
'''
    if render_marker not in html:
        raise RuntimeError("V1 product guide: render marker not found")
    html = html.replace(render_marker, guide_function + render_marker, 1)

    render_route_marker = "chip.textContent=identity.label+' · '+(session.name||'');identityButton.hidden=false;const path=location.pathname;if(path==='/v1'||path==='/v1/'){pendingIdentityReturnPath='';chooseIdentity();return}if(path.includes('/student'))await studentPage();else if(path.includes('/history'))await historyPage();else if(path.includes('/transition'))transitionPage();else await workspace()"
    render_route_replacement = "chip.textContent=identity.label+' · '+(session.name||'');identityButton.hidden=false;guideButton.hidden=false;const path=location.pathname;if(path==='/v1'||path==='/v1/'){pendingIdentityReturnPath='';chooseIdentity();return}if(localStorage.getItem(GUIDE_KEY)!=='1'&&path!=='/v1/guide'){const target=path+location.search;history.replaceState({},'', '/v1/guide?first=1&return='+encodeURIComponent(target));productGuidePage();return}if(path.includes('/guide'))productGuidePage();else if(path.includes('/student'))await studentPage();else if(path.includes('/history'))await historyPage();else if(path.includes('/transition'))transitionPage();else await workspace()"
    if render_route_marker not in html:
        raise RuntimeError("V1 product guide: render route marker not found")
    html = html.replace(render_route_marker, render_route_replacement, 1)

    click_marker = "identityButton.onclick=chooseIdentity;"
    click_replacement = "guideButton.onclick=()=>navigate('/v1/guide');identityButton.onclick=chooseIdentity;"
    if click_marker not in html:
        raise RuntimeError("V1 product guide: top guide click marker not found")
    html = html.replace(click_marker, click_replacement, 1)

    css = (
        "<style id='changying_v1_product_guide_css_v1'>"
        "@media (max-width:640px){#guideButton{padding:8px 10px;font-size:12px}.top-actions{gap:6px}"
        ".top-actions .identity-chip{max-width:112px}.top-actions #identityButton{padding:8px 10px}}"
        "</style>"
    )
    return html.replace("</body>", css + f"<!-- {V1_PRODUCT_GUIDE_MARKER} --></body>", 1)


def install_v1_product_guide_patch() -> None:
    if getattr(v1_module, "_product_guide_patch_installed", False):
        return

    original = v1_module.v1_html

    def patched_v1_html() -> str:
        return patch_v1_product_guide(original())

    v1_module.v1_html = patched_v1_html
    if GUIDE_PATH not in v1_module.V1_PATHS:
        v1_module.V1_PATHS = (*v1_module.V1_PATHS, GUIDE_PATH)
    v1_module._product_guide_patch_installed = True


__all__ = [
    "GUIDE_PATH",
    "V1_PRODUCT_GUIDE_MARKER",
    "install_v1_product_guide_patch",
    "patch_v1_product_guide",
]
