"""Local-only writing inventories and review rules; originals are immutable evidence."""
import base64
import hashlib
import io
import json
import posixpath
import re
import zipfile
from xml.etree import ElementTree as ET

from sqlalchemy import select


def writing_inventory(raw, filename, text=""):
    nodes = []
    digest = hashlib.sha256(raw or text.encode()).hexdigest()
    def add(content, part, kind="text", **extra):
        nodes.append(dict(id=hashlib.sha256((digest+part).encode()).hexdigest()[:24],
            text=content, kind=kind, role="pending", status="pending", targets=[],
            source=dict(file=filename, part=part, sha256=digest),
            reason="原文提取；归属与图文关系需教师确认", **extra))
    if filename.lower().endswith('.json'):
        try:
            parsed=json.loads(raw.decode('utf-8-sig'))
            items=parsed.get('items') if isinstance(parsed,dict) else None
            supplied=items[0].get('writingPackage') if isinstance(items,list) and items and isinstance(items[0],dict) else None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError('作文整包不是有效的UTF-8 JSON文件') from exc
        if not isinstance(supplied,dict):
            raise ValueError('作文整包格式不正确：缺少 items[0].writingPackage')
        if not isinstance(supplied.get('nodes'),list) or len(supplied['nodes'])>500:
            raise ValueError('作文整包最多500项素材')
        allowed={'pending','review','model','model_image','picture','method','task','feedback'}
        old_ids={}
        for i,n in enumerate(supplied['nodes']):
            content=n.get('text','')
            if not isinstance(content,str) or len(content)>20000: raise ValueError('整包素材文字超过上限')
            add(content,f'items[0].writingPackage.nodes[{i}]',n.get('kind','text'))
            new=nodes[-1];old_ids[str(n.get('id',i))]=new['id']
            new['role']=n.get('role') if n.get('role') in allowed else 'pending'
            new['reason']='作文整包声明的素材归属，重新导入后需重新审核'
            declared=n.get('source')
            if isinstance(declared,dict):
                new['declaredSource']={key:str(declared[key])[:300] for key in ('file','part','sha256') if key in declared}
            if n.get('kind')=='table' and isinstance(n.get('rows'),list):
                new['rows']=n['rows'][:100]
            if n.get('kind')=='image' and isinstance(n.get('contexts'),list):
                new['contexts']=n['contexts'][:100]
            if n.get('dataUrl'):
                if not re.fullmatch(r'data:image/(?:png|jpeg);base64,[A-Za-z0-9+/]+={0,2}',n['dataUrl']):
                    raise ValueError('图片必须为内嵌PNG或JPEG')
                if len(n['dataUrl'])>12*1024*1024: raise ValueError('整包单图过大')
                from PIL import Image
                with Image.open(io.BytesIO(base64.b64decode(n['dataUrl'].split(',',1)[1]))) as im: im.verify()
                new.update(kind='image',dataUrl=n['dataUrl'])
        for n,source in zip(nodes,supplied['nodes']):
            n['targets']=[old_ids[t] for t in source.get('targets',[]) if t in old_ids]
        return dict(kind='writing',title=str(supplied.get('title',''))[:180],nodes=nodes,approved=False,history=[],
            source=dict(file=filename,sha256=digest),originalNodes=json.loads(json.dumps(nodes)))
    if filename.lower().endswith(".docx"):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if sum(i.file_size for i in archive.infolist()) > 80*1024*1024:
                raise ValueError("解压后超过80MB，请拆分教案")
            w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
            r = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
            rels = {}
            for entry in archive.namelist():
                if entry == "word/_rels/document.xml.rels":
                    rels = {e.attrib['Id']:posixpath.normpath('word/'+e.attrib['Target'])
                            for e in ET.fromstring(archive.read(entry)) if e.attrib.get('TargetMode') != 'External'}
            root = ET.fromstring(archive.read("word/document.xml"))
            body = root.find(w+"body")
            contexts = {}
            for index, block in enumerate(body):
                paragraphs = ["".join(t.text or "" for t in p.iter(w+"t")) for p in block.iter(w+"p")]
                content = "\n".join(paragraphs).strip()
                refs = [rels[v] for e in block.iter() for k,v in e.attrib.items()
                        if k in (r+'embed', r+'id') and v in rels]
                for part in refs:
                    contexts.setdefault(part, []).append(dict(bodyIndex=index, text=content))
                if content:
                    add(content, f"word/document.xml#body:{index}", "table" if block.tag == w+'tbl' else "text")
                    if block.tag == w+'tbl':
                        nodes[-1]['rows']=[["\n".join("".join(t.text or '' for t in p.iter(w+'t')) for p in cell.iter(w+'p'))
                            for cell in row.findall(w+'tc')] for row in block.findall(w+'tr')]
            media_parts=[part for part in archive.namelist() if part.startswith('word/media/') and not part.endswith('/')]
            media_parts.sort(key=lambda part: (min((c['bodyIndex'] for c in contexts.get(part,[])),default=10**9),part))
            for part in media_parts:
                blob = archive.read(part)
                ext = part.rsplit('.',1)[-1].lower()
                mime = {'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg'}.get(ext)
                add("", part, "image" if mime else "unsupported", contexts=contexts.get(part, []),
                    dataUrl=f"data:{mime};base64,"+base64.b64encode(blob).decode() if mime else "",
                    originalBase64=base64.b64encode(blob).decode(), mediaSha256=hashlib.sha256(blob).hexdigest())
    else:
        for i, line in enumerate(text.splitlines()):
            if line.strip(): add(line, f"text:{i+1}")
    model_start_re = re.compile(r'范文展示|范文赏析|范文导览|范文引路|优秀范文|例文赏析')
    section_break_re = re.compile(
        r'特色好开头|特色好结尾|【佳作】|佳作赏析|第[一二三四五六七八九十\d]+单元|'
        r'写作技法|写作方法|技法梳理|写法指导|审题指导|看图写话|随堂练习|写作任务|习作要求|课后反馈'
    )
    method_option_re = re.compile(r'^[A-F][\.、\s]?[\u4e00-\u9fff]')
    in_model = False
    for n in nodes:
        t = n['text'].strip()
        if n['kind'] in ('image','unsupported'): continue
        is_model_heading = bool(model_start_re.search(t))
        if is_model_heading:
            in_model = True
            continue
        is_method_option = bool(method_option_re.match(t)) or len(re.findall(r'[A-F][\.、\s]?[\u4e00-\u9fff]{2,}', t)) >= 2
        if is_method_option:
            in_model = False
            n.update(role='method', reason='含写作方法选项/旁批；已与范文正文分离，请核对')
            continue
        if section_break_re.search(t):
            in_model = False
        if in_model:
            n.update(role='model', reason='位于范文标题之后；原件分行不一定是自然段，请核对合并')
        elif any(k in t for k in ('观察','顺序','感官','修辞','动静','情感','开头','结尾','描写','方法','技法')):
            n.update(role='method', reason='含写作方法关键词；需核对方法与例句')
    title=''
    topic_source=None
    for n in nodes:
        if n['kind'] in ('image','unsupported'): continue
        t = n['text']
        m = re.search(r'(?:写作主题|习作题目|作文题目|写作题目|习作主题|本次习作)[:：]\s*([^\n]{2,40})', t)
        if m:
            title = m.group(1).strip('《》“”"\' ')
            topic_source = n
            break
    if not title:
        for n in nodes:
            if n['kind'] in ('image','unsupported'): continue
            t = n['text']
            if any(k in t for k in ('主题','题目','习作','作文','写作')):
                m = re.search(r'《([^》]{2,30})》', t)
                if m:
                    title = m.group(1).strip()
                    topic_source = n
                    break
    if not title:
        heading = next((n for n in nodes if '最喜欢的季节' in n['text']), None)
        if heading:
            title = '我最喜欢的季节'
            topic_source = heading
    if title and topic_source:
        add(title, topic_source['source']['part']+'#theme')
        nodes[-1].update(role='task', reason='摘自原文写作主题标题；主题仍需教师确认')
    return dict(kind='writing', title=title, nodes=nodes, approved=False, history=[],
                source=dict(file=filename, sha256=digest), originalNodes=json.loads(json.dumps(nodes)))


def writing_package(implementation, db, lesson_id):
    from changying.web.weekend_paired_import import register_paired_import_tables
    table = register_paired_import_tables(implementation)['lesson_import_pairs']
    rows = db.execute(select(table).where(table.c.lesson_id==lesson_id).order_by(table.c.id.desc())).all()
    for row in rows:
        data=json.loads(row.meta_json)
        if data.get('kind')=='writing': return row, data
    return None, None


def writing_readiness(package):
    from changying.services.weekend_stages import stages_for
    nodes=package.get('nodes',[]) if package else []
    active=[n for n in nodes if n.get('status')!='ignored']
    confirmed=[n for n in active if n.get('status')=='confirmed']
    requirements={1:[('review','回顾内容')],2:[('model','范文正文'),('model_image','范文配图组')],
        3:[('picture','看图写话图片组')],4:[('method','写作方法组')],5:[('task','一个写作主题')],6:[('feedback','反馈要求')]}
    reasons=[]; stages=[]
    for spec in stages_for('writing'):
        truly_missing=[label for role,label in requirements[spec['no']] if not any(n.get('role')==role for n in active)]
        unconfirmed=[label for role,label in requirements[spec['no']] if any(n.get('role')==role for n in active) and not any(n.get('role')==role for n in confirmed)]
        state='缺少素材' if truly_missing else ('待确认' if unconfirmed or not (package and package.get('approved')) else '已审核')
        if truly_missing: reasons.append(spec['name']+'：缺少'+ '、'.join(truly_missing))
        elif unconfirmed: reasons.append(spec['name']+'：待确认'+ '、'.join(unconfirmed))
        stages.append(dict(no=spec['no'],name=spec['name'],status=state,missing=truly_missing))
    pending=sum(n.get('status')!='confirmed' for n in active)
    if pending: reasons.append(f'{pending}项素材待确认或忽略')
    model_text=''.join(n.get('text','') for n in confirmed if n.get('role')=='model')
    if len(re.sub(r'\s+','',model_text)) < 120:
        reasons.append('范文正文不足一篇，请核对完整正文与段落')
    if sum(n.get('role')=='task' for n in confirmed)!=1: reasons.append('随堂练习必须恰有一个主题')
    ids={n['id']:n for n in confirmed}
    for n in confirmed:
        if n.get('role')=='pending': reasons.append('未识别素材请分配归属或明确忽略')
        if n.get('role') in ('task','model') and (n.get('kind') not in ('text','table') or not n.get('text','').strip()):
            reasons.append('范文和主题必须有可读正文')
        if n.get('role') in ('model_image','picture') and (n.get('kind')!='image' or not n.get('dataUrl')):
            reasons.append('图片组必须使用真实图片')
        if n.get('role')=='model_image' and (not n.get('targets') or any(ids.get(t,{}).get('role')!='model' for t in n['targets'])):
            reasons.append('范文配图需绑定已确认的范文段落')
        if n.get('role') not in ('model_image','picture') and not n.get('text','').strip() and not n.get('dataUrl'):
            reasons.append('已确认素材不能为空')
    return dict(courseType='writing', pendingMaterials=pending, stageReadiness=stages,
        coursewareGenerated=bool(nodes), coursewareApproved=bool(package and package.get('approved') and not reasons),
        canStart=bool(package and package.get('approved') and not reasons),
        startReasons=reasons+([] if package and package.get('approved') else ['作文课程尚未审核通过']))


def writing_task_open(implementation, db, session):
    from changying.services.weekend_course_types import frozen_session
    frozen=frozen_session(db,implementation,session.id)
    return bool(frozen and frozen['lesson'].get('writingPackage') and
                frozen['lesson'].get('writingState',{}).get('taskOpened'))


def writing_stage_slides(package, stage_no):
    """Build native big-screen slide cards for a writing stage from the frozen package."""
    if not isinstance(package, dict):
        return []
    title = str(package.get('title') or '作文课').strip()[:60]
    confirmed = [n for n in package.get('nodes', []) if n.get('status') == 'confirmed']
    stage = int(stage_no or 0)
    slides = []

    if stage == 1:
        items = [str(n.get('text') or '').strip() for n in confirmed if n.get('role') == 'review' and str(n.get('text') or '').strip()]
        if items:
            slides.append({'heading': f'{title} · 点名与回顾', 'layout': 'standard', 'body': items[:12]})
    elif stage == 2:
        models = [n for n in confirmed if n.get('role') == 'model' and str(n.get('text') or '').strip()]
        images = [n for n in confirmed if n.get('role') == 'model_image' and n.get('dataUrl')]
        essay_title = title
        body_models = list(models)
        if body_models:
            first_txt = str(body_models[0].get('text') or '').strip()
            if len(first_txt) <= 18 and not re.search(r'[。！？，]', first_txt):
                essay_title = first_txt
                body_models = body_models[1:] or body_models
        used_ids = set()
        for idx, p in enumerate(body_models[:12]):
            bound = [img for img in images if p.get('id') in (img.get('targets') or [])]
            for img in bound:
                used_ids.add(img.get('id'))
            slide = {
                'heading': f'范文导览 · {essay_title}' if len(body_models) == 1 else f'范文导览 · {essay_title}（{idx + 1}/{len(body_models)}）',
                'layout': 'reading' if bound else 'standard',
                'body': [str(p.get('text') or '').strip()[:500]],
            }
            if bound:
                slide['figure'] = {'type': 'uploaded_image', 'data_url': bound[0]['dataUrl'], 'alt': f'{essay_title}配图'}
            slides.append(slide)
        for img in images:
            if img.get('id') not in used_ids and len(slides) < 12:
                slides.append({
                    'heading': f'范文配图 · {essay_title}',
                    'layout': 'scene',
                    'body': [],
                    'figure': {'type': 'uploaded_image', 'data_url': img['dataUrl'], 'alt': '范文配图'},
                })
    elif stage == 3:
        pics = [n for n in confirmed if n.get('role') == 'picture' and n.get('dataUrl')]
        for idx, pic in enumerate(pics[:12]):
            caption = str(pic.get('text') or '').strip()
            slides.append({
                'heading': f'看图写话（图 {idx + 1}/{len(pics)}）',
                'layout': 'scene',
                'body': [caption[:500]] if caption else ['仔细观察画面：按一定顺序说说你看到了什么，加上感官与联想。'],
                'figure': {'type': 'uploaded_image', 'data_url': pic['dataUrl'], 'alt': f'看图写话配图 {idx + 1}'},
            })
    elif stage == 4:
        methods = [str(n.get('text') or '').strip() for n in confirmed if n.get('role') == 'method' and str(n.get('text') or '').strip()]
        chunk = 4
        total_pages = max(1, (len(methods) + chunk - 1) // chunk) if methods else 0
        for p_idx in range(min(total_pages, 12)):
            part = methods[p_idx * chunk:(p_idx + 1) * chunk]
            slides.append({
                'heading': '技法梳理' if total_pages == 1 else f'技法梳理（{p_idx + 1}/{total_pages}）',
                'layout': 'standard',
                'body': [t[:500] for t in part],
            })
    elif stage == 5:
        tasks = [str(n.get('text') or '').strip() for n in confirmed if n.get('role') == 'task' and str(n.get('text') or '').strip()]
        if tasks:
            slides.append({
                'heading': '随堂练习 · 写作主题',
                'layout': 'standard',
                'body': [f'《{tasks[0]}》', '请围绕本次写作主题构思提纲并完成习作，完成后可拍照上传提交。'],
            })
    elif stage == 6:
        fbs = [str(n.get('text') or '').strip() for n in confirmed if n.get('role') == 'feedback' and str(n.get('text') or '').strip()]
        if fbs:
            slides.append({'heading': '课后反馈与修改重点', 'layout': 'standard', 'body': [t[:500] for t in fbs[:12]]})

    return slides[:12]
