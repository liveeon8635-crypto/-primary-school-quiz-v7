"""Self-contained paper pack for an existing classroom; no extra student archive."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from html import escape

from fastapi import HTTPException
from sqlalchemy import func, select

from changying.services.weekend_roster import session_class, session_roster
from changying.services.weekend_stages import STAGES


def backup_material(impl, db, session, *, include_files=False):
    from changying.web.weekend_written import register_written_tables
    if session_class(impl, db, session) is None:
        raise HTTPException(409, '请先为原课堂指定班级，再生成备用包')
    lesson = db.get(impl.TeachingLesson, session.lesson_id)
    if lesson is None or lesson.school_id != session.school_id:
        raise HTTPException(404, '没有找到原教案')
    questions = []
    for q in db.scalars(select(impl.TeachingQuestion).where(impl.TeachingQuestion.school_id == session.school_id,
            impl.TeachingQuestion.lesson_id == session.lesson_id, impl.TeachingQuestion.active.is_(True)).order_by(impl.TeachingQuestion.id).limit(30)):
        options = json.loads(q.options_json or '[]')
        if not isinstance(options, list) or not 0 <= q.correct_index < len(options):
            raise HTTPException(409, '有题目的选项或答案不完整，请先审核')
        questions.append(dict(kind='choice', id=q.id, stem=q.stem, options=options, selected=q.correct_index,
            reference=str(options[q.correct_index]), explanation=q.explanation or '', level=q.level,
            knowledge=q.knowledge or lesson.core_target or ''))
    wq = register_written_tables(impl)['questions']
    for q in db.execute(select(wq).where(wq.c.school_id == session.school_id, wq.c.session_id == session.id,
            wq.c.teacher_id == session.teacher_id).order_by(wq.c.id)):
        questions.append(dict(kind='written', id=q.id, stem=q.stem, reference=q.reference,
            explanation='', level='开放作答', knowledge=lesson.core_target or ''))
    if not questions:
        raise HTTPException(409, '请先审核或添加本节课题目')
    roster = [dict(id=i, name=n) for i, (n, _) in sorted(session_roster(impl, db, session).items())]
    if not roster:
        raise HTTPException(409, '本节课堂没有学生')
    if (len(lesson.reading_plan or '')+sum(len(q['stem'])+sum(len(str(x)) for x in q.get('options',[])) for q in questions))*len(roster)>4_000_000:
        raise HTTPException(413,'本课堂打印内容过大，请减少本次题目或分班准备')
    resource = impl.TeachingResource
    resources = db.execute(select(resource.id,resource.file_name,resource.file_ext,resource.sha256,
        func.length(resource.file_data).label('bytes')).where(resource.school_id == session.school_id,
        resource.lesson_id == session.lesson_id, func.lower(resource.file_ext).in_(['pdf','.pdf','docx','.docx','pptx','.pptx','txt','.txt','md','.md','png','.png','jpg','.jpg','jpeg','.jpeg'])).order_by(resource.id).limit(21)).all()
    resources = [r for r in resources if str(r.file_ext or '').lower().lstrip('.') in
                 ('pdf','docx','pptx','txt','md','png','jpg','jpeg')]
    if len(resources)>20 or sum(int(r.bytes or 0) for r in resources)>30*1024*1024:
        raise HTTPException(413, '关联原文件超过20份或30MB，请先整理本课资源')
    files = []
    for r in resources:
        item = dict(id=r.id,name=r.file_name,extension=str(r.file_ext).lower().lstrip('.'),sha256=r.sha256)
        if include_files:
            item['data'] = bytes(db.get(resource,r.id).file_data or b'')
            if r.sha256 and hashlib.sha256(item['data']).hexdigest()!=r.sha256:
                raise HTTPException(409,'原文件校验不一致，请检查教案附件')
        files.append(item)
    material = dict(sessionId=session.id, lessonId=lesson.id, title=session.title, subject=lesson.subject,
        className=session_class(impl, db, session).class_name, roster=roster, questions=questions,
        lesson={key: getattr(lesson, key) for key in ('core_target', 'duration_min', 'teacher_plan', 'reading_plan',
            'writing_plan', 'examples_json', 'ppt_json', 'closure_training', 'essay_review')},
        resources=[{k: f[k] for k in ('id', 'name', 'sha256')} for f in files])
    digest = hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    material.update(packageHash=digest, version=digest[:16])
    return material, files


def print_document(title, body):
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>'+escape(title)+
        '</title><style>@page{size:A4;margin:16mm}*{box-sizing:border-box}body{font:15px/1.65 sans-serif;color:#111;max-width:180mm;margin:auto}'
        'h1{font-size:23px}h2{font-size:19px;margin-top:22px}h3{font-size:16px}p,pre{white-space:pre-wrap;overflow-wrap:anywhere}'
        'pre{font:inherit}table{width:100%;border-collapse:collapse}td,th{border:1px solid #888;padding:6px;vertical-align:top}'
        'section{break-before:page;page-break-before:always}section:first-child{break-before:auto;page-break-before:auto}h2,h3{break-after:avoid;page-break-after:avoid}.question{margin:20px 0}.space{height:40mm;border-bottom:1px solid #ccc}'
        '.meta{font-size:12px}svg{max-width:100%}@media print{body{max-width:none}}</style></head><body>'+body+'</body></html>')


def backup_zip(material, files, checkpoint):
    m = material
    heading = '<h1>'+escape(m['title'])+'</h1><p class="meta">原课堂 '+str(m['sessionId'])+' · '+escape(m['className'])+' · 备用包版本 '+m['version']+'</p>'
    stages = ''.join('<tr><td>'+str(s['no'])+'</td><td>'+escape(s['name'])+'</td><td>'+escape(s['goal'])+'</td></tr>' for s in STAGES)
    teacher = heading+'<p>课前先解压并逐份打印。教师稿和参考答案不要发给学生。发生故障时按记录卡上的环节／页码／题号继续，不另建课堂。</p>'
    teacher += '<p>课程时长：'+str(m['lesson']['duration_min'])+'分钟；以下环节编号与线上一致，具体用时按原教案执行。</p><table>'+stages+'</table>'
    for key, label in [('core_target','教学目标'),('teacher_plan','原教师教案'),('reading_plan','阅读内容'),('writing_plan','写作内容'),('ppt_json','知识点／课件原文'),('examples_json','例题原文'),('closure_training','课后练习'),('essay_review','习作讲评')]:
        raw = m['lesson'][key]
        if key.endswith('_json'):
            try:
                data = json.loads(raw or '[]')
                raw = '\n\n'.join(json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else str(x) for x in data)
            except (ValueError, TypeError): pass
        if raw: teacher += '<h2>'+label+'</h2><pre>'+escape(str(raw))+'</pre>'
    teacher += '<h2>备课核对</h2><p>基础／提升／挑战按题目原有层级选择，先完成自己的题，再挑一道已完成题讲思路。提前备好铅笔、直尺、彩笔、计时工具和纸质方格图。</p>'
    teacher += '<p>正文完整保留；系统识别文字不等于原图。涉及几何图、外链图片或教具时，请核对 resources 中的原文件并提前打印；未关联原文件的图须另行备齐。</p>'
    teacher += '<p>联网恢复后回到原课堂，先补录、核对，再使用原有积分结算。重复提交不会重复建档或发分；已有线上答案保留，已结算课堂不再接收补录。</p>'
    student = ''
    answers = heading+'<h2>教师参考答案（不要发给学生）</h2>'
    for pupil in m['roster']:
        student += '<section>'+heading+'<h2>姓名：'+escape(pupil['name'])+'　学生编号：'+str(pupil['id'])+'</h2><p>先独立作答；用过提示请记录0／1／2／3级。完成后可选一道题准备讲解。</p>'
        if m['lesson']['reading_plan']:
            student += '<h2>阅读材料与要求</h2><pre>'+escape(m['lesson']['reading_plan'])+'</pre>'
        for index, q in enumerate(m['questions'], 1):
            student += '<div class="question"><h3>第'+str(index)+'题 · '+escape({'A':'挑战','B':'提升','C':'基础'}.get(str(q['level']),str(q['level'])))+' · '+q['kind']+':'+str(q['id'])+'</h3><pre>'+escape(q['stem'])+'</pre>'
            for i, option in enumerate(q.get('options', [])):
                student += '<p>'+chr(65+i)+'. '+escape(str(option))+'</p>'
            student += '<p>提示级别：0　1　2　3</p><div class="space"></div></div>'
        student += '<p>我的讲解准备：先说明什么？用了什么方法？哪里容易出错？</p><div class="space"></div></section>'
    for index, q in enumerate(m['questions'], 1):
        answers += '<div class="question"><h3>第'+str(index)+'题 · '+q['kind']+':'+str(q['id'])+'</h3><pre>'+escape(q['stem'])+'</pre><p>参考答案：'+escape(q.get('reference') or '尚未填写，请教师备课时补齐评分要点')+'</p><pre>'+escape(q.get('explanation',''))+'</pre></div>'
    card = heading+'<h2>故障接续记录卡</h2><p>导出时线上位置：'+escape(checkpoint)+'。故障发生时请填写下面实际位置。</p><p>发生时间：________　环节编号：____　课件页码：____　练习题号：____</p><p>恢复位置：________　已完成环节：________　纸质授课实际时长：________</p><table><tr><th>学生／编号</th><th>题号／原题ID</th><th>作答或答卷编号</th><th>提示级别</th><th>批改与备注</th></tr>'
    record = io.StringIO(newline=''); writer = csv.writer(record)
    writer.writerow(['classroom_id','package_version','student_id','student_name','question_kind','question_id','question_no','answer','hint_level','review','note'])
    for pupil in m['roster']:
        for index, q in enumerate(m['questions'], 1):
            card += '<tr><td>'+escape(pupil['name'])+' / '+str(pupil['id'])+'</td><td>'+str(index)+' / '+q['kind']+':'+str(q['id'])+'</td><td>　</td><td>　</td><td>　</td></tr>'
            # Prefix spreadsheet formulas from user-controlled names.
            name = str(pupil['name']);name = "'"+name if name[:1] in '=+-@\t\r' else name
            writer.writerow([m['sessionId'],m['version'],pupil['id'],name,q['kind'],q['id'],index,'','','',''])
    card += '</table><p>联网后：原课堂 → 纸质备用与补录。逐条核对版本、学生和原题，再补录。CSV仅作记录，不会自动上传。</p>'
    grid = heading+'<h2>通用方格操作纸</h2><p>可按原题在方格中补画、旋转并标注点名；此纸不是原题图的替代品。</p><svg xmlns="http://www.w3.org/2000/svg" width="600" height="600" viewBox="0 0 600 600">'
    grid += ''.join('<path d="M '+str(x)+' 0 V 600" stroke="#999" stroke-width=".5"/>' for x in range(0,601,20))
    grid += ''.join('<path d="M 0 '+str(y)+' H 600" stroke="#999" stroke-width=".5"/>' for y in range(0,601,20))+'</svg>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for filename, title, body in [('01-teacher.html','教师教案',teacher),('02-students.html','学生分层练习',student),('03-answers.html','教师参考答案',answers),('04-records.html','故障接续记录卡',card),('05-grid.html','方格操作纸',grid)]:
            z.writestr(filename, print_document(title,body))
        z.writestr('06-records.csv', '\ufeff'+record.getvalue())
        z.writestr('manifest.json', json.dumps(m,ensure_ascii=False,indent=2))
        z.writestr('README.txt','教师专用，勿把整个压缩包发给学生。\n课前解压，浏览器打开HTML，打印或另存PDF；文件不依赖网络。\n原图优先打印resources中的原文件。\n故障时记下环节／页码／题号，纸质接续。\n恢复联网后在原课堂补录，核对后统一结算积分。\n本功能不提供断网自动保存或自动同步。')
        for f in files:
            z.writestr('resources/'+str(f['id'])+'.'+f['extension'],f['data'])
    return out.getvalue()
