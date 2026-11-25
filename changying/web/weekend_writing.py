"""Writing-specific review and classroom APIs backed by existing versioned storage."""
import base64
import copy
import hashlib
import io
import json
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import insert, select, update

from changying.services.writing_lesson import writing_inventory, writing_package, writing_readiness


class WritingSave(BaseModel):
    expectedRevision: int = Field(ge=1)
    nodes: list[dict[str, Any]] = Field(max_length=500)
    title: str = Field(max_length=180)
    approve: bool = False


class WritingImageReview(BaseModel):
    expectedRevision: int = Field(ge=1)
    targets: list[str] = Field(max_length=500)


class WritingBulkReview(BaseModel):
    expectedRevision: int = Field(ge=1)
    action: Literal["confirm_assigned", "ignore_unassigned"]


class WritingRelease(BaseModel):
    expectedRevision: int = Field(ge=0)
    nodeIds: list[str] = Field(max_length=500)


class WritingFeedback(BaseModel):
    expectedRevision: int = Field(ge=0)
    studentId: int
    comment: str = Field(max_length=4000)
    nextStep: str = Field(max_length=2000)
    publish: bool = False


class WritingAttendance(BaseModel):
    expectedRevision: int = Field(ge=0)
    studentId: int
    present: bool


def store_writing_package(implementation, db, user, lesson, package):
    from changying.web.weekend_paired_import import register_paired_import_tables
    table=register_paired_import_tables(implementation)['lesson_import_pairs']
    now=datetime.utcnow()
    source=package.get('source',{})
    db.execute(insert(table).values(school_id=user.school_id,lesson_id=lesson.id,
        teacher_file_name=source.get('file','course-package')[:180],teacher_sha256=source.get('sha256',''),
        student_file_name='',student_sha256='',meta_json=json.dumps(package,ensure_ascii=False),
        revision=1,created_by=user.id,created_at=now,updated_at=now))


def install_weekend_writing(implementation):
    from changying.web.weekend_paired_import import register_paired_import_tables
    from changying.services.weekend_course_types import register_weekend_course_type_tables, course_type_for
    from changying.web.weekend_views import register_weekend_tables
    from changying.web.weekend_written import register_written_tables
    from changying.services.weekend_roster import student_in_session, session_roster
    from changying.web.writing_pages import writing_page
    router=APIRouter()
    pairs=register_paired_import_tables(implementation)['lesson_import_pairs']
    frozen=register_weekend_course_type_tables(implementation)['frozen']
    sessions=register_weekend_tables(implementation)['sessions']
    written=register_written_tables(implementation)
    current_user,get_db=implementation.current_user,implementation.get_db

    def completion(db,row,data,student):
        logs=implementation.Base.metadata.tables['weekend_stage_log']
        visited=set(db.scalars(select(logs.c.stage_no).where(logs.c.session_id==row.id)))
        opened=set(data.get('writingState',{}).get('openedRoles',[]))
        submitted=db.scalar(select(written['submission_versions'].c.id).where(
            written['submission_versions'].c.session_id==row.id,written['submission_versions'].c.student_id==student).limit(1))
        return dict(attendance=data.get('writingState',{}).get('attendance',{}).get(str(student)),
                    model=2 in visited and {'model','model_image'}<=opened,
                    picture=3 in visited and 'picture' in opened,
                    methods=4 in visited and 'method' in opened,submitted=bool(submitted))

    def lesson_context(db,u,lid):
        implementation.need(u,'teacher')
        lesson=db.get(implementation.TeachingLesson,lid)
        if lesson is None or lesson.school_id!=u.school_id: raise HTTPException(404,'没有找到课程')
        if course_type_for(db,implementation,lesson)!='writing': raise HTTPException(409,'请先保存作文课课型')
        return lesson

    def class_context(db,u,sid):
        row=db.execute(select(sessions).where(sessions.c.id==sid,sessions.c.school_id==u.school_id).with_for_update()).first()
        if row is None or not (u.role=='teacher' and row.teacher_id==u.id or u.role=='student' and student_in_session(implementation,db,row,u.id)):
            raise HTTPException(404,'没有找到课堂')
        snapshot=db.execute(select(frozen).where(frozen.c.session_id==sid)).first()
        data=json.loads(snapshot.lesson_json) if snapshot else {}
        if not data.get('writingPackage'): raise HTTPException(409,'该课堂没有冻结的作文课程包')
        return row,snapshot,data

    def save_state(db,snapshot,data,expected):
        state=data.setdefault('writingState',{'revision':0,'open':[],'feedback':{}})
        if state['revision']!=expected: raise HTTPException(409,'课堂状态已更新，请刷新')
        state['revision']+=1
        changed=db.execute(update(frozen).where(frozen.c.session_id==snapshot.session_id,
            frozen.c.lesson_json==snapshot.lesson_json).values(lesson_json=json.dumps(data,ensure_ascii=False)))
        if changed.rowcount!=1: raise HTTPException(409,'课堂已被其他操作更新，请刷新')
        db.commit()

    @router.get('/teacher/weekend/lessons/{lid}/writing')
    def get_package(lid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        lesson_context(db,u,lid)
        row,package=writing_package(implementation,db,lid)
        return dict(package=package,revision=row.revision if row else 0,readiness=writing_readiness(package))

    @router.post('/teacher/weekend/lessons/{lid}/writing/bulk-review')
    def bulk_review_package(lid:int,b:WritingBulkReview,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        lesson_context(db,u,lid)
        row,package=writing_package(implementation,db,lid)
        if row is None or row.revision!=b.expectedRevision:
            raise HTTPException(409,'课程已更新，请刷新后重新核对')
        nodes=package.get('nodes',[])
        if b.action=='confirm_assigned':
            selected=[n for n in nodes if n.get('status')=='pending' and n.get('role') not in ('pending',None,'')]
            for n in selected: n['status']='confirmed'
            label='教师批量确认已分类素材'
        else:
            selected=[n for n in nodes if n.get('status')=='pending' and n.get('role') in ('pending',None,'')]
            for n in selected: n['status']='ignored'
            label='教师批量忽略未分类素材'
        if not selected:
            return dict(updated=0,package=package,revision=row.revision,readiness=writing_readiness(package))
        package['approved']=False
        package['history']=package.get('history',[])+[dict(revision=row.revision,at=datetime.utcnow().isoformat(),
            by=u.id,action=b.action,updated=len(selected),title=package.get('title',''))]
        changed=db.execute(update(pairs).where(pairs.c.id==row.id,pairs.c.revision==b.expectedRevision).values(
            meta_json=json.dumps(package,ensure_ascii=False),revision=row.revision+1,updated_at=datetime.utcnow()))
        if changed.rowcount!=1:
            db.rollback()
            raise HTTPException(409,'课程已被其他操作更新，请刷新后重试')
        db.commit()
        row,package=writing_package(implementation,db,lid)
        return dict(updated=len(selected),action=label,package=package,revision=row.revision,
                    readiness=writing_readiness(package))

    @router.post('/teacher/weekend/lessons/{lid}/writing/images/{node_id}/confirm')
    def confirm_image(lid:int,node_id:str,b:WritingImageReview,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        lesson_context(db,u,lid)
        row,package=writing_package(implementation,db,lid)
        if row is None or row.revision!=b.expectedRevision:
            raise HTTPException(409,'素材已更新，请刷新后重新核对')
        nodes=package.get('nodes',[])
        image=next((n for n in nodes if n.get('id')==node_id and n.get('kind')=='image'
                    and n.get('role') in ('model_image','picture') and n.get('status')!='ignored'),None)
        if image is None:
            raise HTTPException(404,'本课没有这张待审核配图')
        targets=image.get('targets',[])
        if image['role']=='model_image':
            models={n['id'] for n in nodes if n.get('role')=='model' and n.get('status')!='ignored'}
            targets=list(dict.fromkeys(b.targets))
            if not targets or not models.issuperset(targets):
                raise HTTPException(422,'请选择本课有效的范文段落')
        if image.get('status')=='confirmed' and targets==image.get('targets',[]):
            return {'revision':row.revision}
        package.setdefault('history',[]).append(dict(revision=row.revision,at=datetime.utcnow().isoformat(),
            by=u.id,action='confirm_image',nodeId=node_id,previousStatus=image.get('status'),
            previousTargets=image.get('targets',[]),previousApproved=package.get('approved',False)))
        image.update(status='confirmed',targets=targets)
        package['approved']=False
        changed=db.execute(update(pairs).where(pairs.c.id==row.id,pairs.c.revision==b.expectedRevision).values(
            meta_json=json.dumps(package,ensure_ascii=False),revision=row.revision+1,updated_at=datetime.utcnow()))
        if changed.rowcount!=1:
            db.rollback()
            raise HTTPException(409,'素材已更新，请刷新后重新核对')
        db.commit()
        return {'revision':b.expectedRevision+1}

    @router.post('/teacher/weekend/lessons/{lid}/writing/imported-images')
    def import_confirmed_images(lid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        """Copy reviewed picture assets into the writing package as pending, teacher-reviewable nodes."""
        lesson=lesson_context(db,u,lid)
        row,package=writing_package(implementation,db,lid)
        if row is None: raise HTTPException(409,'请先导入作文教案或作文课整包')
        materials=register_weekend_course_type_tables(implementation)['materials']
        imported=db.execute(select(materials).where(
            materials.c.school_id==int(u.school_id),materials.c.lesson_id==int(lesson.id),
            materials.c.status=='confirmed',materials.c.relationship.in_(['model_essay','picture_writing'])
        ).order_by(materials.c.sort_order,materials.c.id)).all()
        existing={n.get('importedMaterialId') for n in package.get('nodes',[]) if n.get('importedMaterialId')}
        created=0
        for material in imported:
            if int(material.id) in existing: continue
            role='model_image' if material.relationship=='model_essay' else 'picture'
            nid='imported-material-'+str(material.id)
            package.setdefault('nodes',[]).append(dict(id=nid,kind='image',role=role,status='pending',text='',
                targets=[],dataUrl=material.data_url,importedMaterialId=int(material.id),
                source=dict(file=material.source_file,part=material.source_part,sha256=material.source_sha256),
                reason='来自已确认的导入图片；已加入作文包，仍需教师确认并完成范文段落绑定。'))
            created+=1
        if not created: return dict(created=0,package=package,revision=row.revision,readiness=writing_readiness(package))
        package['approved']=False
        changed=db.execute(update(pairs).where(pairs.c.id==row.id,pairs.c.revision==row.revision).values(
            meta_json=json.dumps(package,ensure_ascii=False),revision=row.revision+1,updated_at=datetime.utcnow()))
        if changed.rowcount!=1: raise HTTPException(409,'课程已被其他操作更新，请刷新后重试')
        db.commit()
        row,package=writing_package(implementation,db,lid)
        return dict(created=created,package=package,revision=row.revision,readiness=writing_readiness(package))

    @router.put('/teacher/weekend/lessons/{lid}/writing')
    def save_package(lid:int,b:WritingSave,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        lesson=lesson_context(db,u,lid)
        row,old=writing_package(implementation,db,lid)
        if row is None or row.revision!=b.expectedRevision: raise HTTPException(409,'课程已更新，请刷新后重新核对')
        allowed={'review','model','model_image','picture','method','task','feedback','pending'}
        old_nodes={n['id']:n for n in old['nodes']}
        nodes=[]; ids=set()
        for raw in b.nodes:
            nid=str(raw.get('id') or uuid.uuid4().hex)
            if nid in ids or len(nid)>80: raise HTTPException(422,'节点标识不能重复')
            ids.add(nid)
            n=copy.deepcopy(old_nodes.get(nid,dict(id=nid,kind='text',source={'file':'教师站内配置','part':nid},reason='教师手动配置')))
            if nid not in old_nodes and raw.get('derivedFrom'):
                parent=old_nodes.get(raw['derivedFrom'])
                if parent is None: raise HTTPException(422,'拆分来源不存在')
                n.update(source=parent['source'],derivedFrom=parent['id'],reason='从原素材拆分；原素材仍保留')
            for key in ('text','role','status','targets'):
                if key in raw: n[key]=raw[key]
            if n.get('role') not in allowed or n.get('status') not in ('pending','confirmed','ignored'):
                raise HTTPException(422,'请选择素材归属与审核状态')
            if not isinstance(n.get('text'),str) or len(n['text'])>20000 or not isinstance(n.get('targets',[]),list):
                raise HTTPException(422,'素材内容或绑定格式不正确')
            if any(not isinstance(v,str) for v in n.get('targets',[])): raise HTTPException(422,'绑定标识格式不正确')
            nodes.append(n)
        # An omitted source remains reviewable; deletion cannot silently discard evidence.
        nodes.extend(n for n in old['nodes'] if n['id'] not in ids)
        package={**old,'title':b.title,'nodes':nodes,'approved':False}
        if b.approve:
            check=writing_readiness({**package,'approved':True})
            if not check['canStart']: raise HTTPException(409,'；'.join(check['startReasons']))
            package['approved']=True
        history_entry=dict(revision=row.revision,at=datetime.utcnow().isoformat(),by=u.id,
                           title=old.get('title',''),approved=old.get('approved',False))
        # Image bytes and source metadata are immutable in this editor. For ordinary
        # review decisions record the previous statuses without duplicating all media.
        status_only=len(nodes)==len(old['nodes']) and all(
            previous=={**current,'status':previous.get('status')} for previous,current in zip(old['nodes'],nodes))
        if status_only:
            history_entry['previousStatuses']={p['id']:p.get('status') for p,n in zip(old['nodes'],nodes)
                                               if p.get('status')!=n.get('status')}
        else:
            history_entry['nodes']=[{k:v for k,v in n.items() if k not in ('dataUrl','originalBase64')} for n in old['nodes']]
        package['history']=old.get('history',[])+[history_entry]
        encoded=json.dumps(package,ensure_ascii=False)
        if len(encoded)>60*1024*1024: raise HTTPException(413,'课程历史超过60MB，请另建课次保留历史')
        changed=db.execute(update(pairs).where(pairs.c.id==row.id,pairs.c.revision==b.expectedRevision).values(
            meta_json=encoded,revision=row.revision+1,updated_at=datetime.utcnow()))
        if changed.rowcount!=1: raise HTTPException(409,'并发修改冲突，请刷新')
        if b.title: lesson.title=b.title
        db.commit()
        return get_package(lid,u,db)

    @router.post('/teacher/weekend/lessons/{lid}/writing/images')
    def add_image(lid:int,expectedRevision:int=Form(...),file:UploadFile=File(...),u:Any=Depends(current_user),db:Any=Depends(get_db)):
        lesson_context(db,u,lid)
        row,package=writing_package(implementation,db,lid)
        if row is None or row.revision!=expectedRevision: raise HTTPException(409,'课程已更新，请刷新')
        raw=file.file.read(8*1024*1024+1)
        if len(raw)>8*1024*1024: raise HTTPException(413,'图片超过8MB')
        from PIL import Image, ImageOps
        try:
            with Image.open(io.BytesIO(raw)) as im:
                image=ImageOps.exif_transpose(im).convert('RGB');image.thumbnail((1800,1800))
                buf=io.BytesIO();image.save(buf,format='JPEG',quality=80)
        except Exception as exc: raise HTTPException(422,'无法读取图片') from exc
        nid=uuid.uuid4().hex
        package['nodes'].append(dict(id=nid,kind='image',role='pending',status='pending',text='',targets=[],
            source=dict(file=file.filename,part=nid,sha256=hashlib.sha256(raw).hexdigest()),reason='教师补充图片，待分配',
            dataUrl='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode(),originalBase64=base64.b64encode(raw).decode()))
        package['approved']=False
        changed=db.execute(update(pairs).where(pairs.c.id==row.id,pairs.c.revision==expectedRevision).values(
            meta_json=json.dumps(package,ensure_ascii=False),revision=row.revision+1,updated_at=datetime.utcnow()))
        if changed.rowcount!=1: raise HTTPException(409,'并发修改冲突')
        db.commit()
        return get_package(lid,u,db)

    @router.get('/weekend/writing/sessions/{sid}')
    def classroom(sid:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        from changying.services.weekend_stages import stages_for
        row,snapshot,data=class_context(db,u,sid)
        package=data['writingPackage'];state=data.get('writingState',{'revision':0,'open':[],'feedback':{}})
        teacher=u.role=='teacher'
        nodes=[{k:n.get(k) for k in ('id','kind','role','text','dataUrl','targets')} for n in package['nodes']
               if n['status']=='confirmed' and (teacher or n['id'] in state['open'])]
        payload=dict(title=package['title'],nodes=nodes,stages=stages_for('writing'),revision=state['revision'],open=state['open'],
            stage=row.current_stage,status=row.status,teacher=teacher)
        if teacher:
            roster=session_roster(implementation,db,row)
            payload['students']=[dict(id=s,name=db.get(implementation.User,s).name) for s in roster]
            payload['feedback']=state['feedback']
            payload['completion']={str(s):completion(db,row,data,s) for s in roster}
        else:
            published=state['feedback'].get(str(u.id),{}).get('published',[])
            payload['feedback']=published[-1] if published else None
        return payload

    @router.post('/teacher/weekend/writing/sessions/{sid}/attendance')
    def attendance(sid:int,b:WritingAttendance,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        implementation.need(u,'teacher')
        row,snapshot,data=class_context(db,u,sid)
        if b.studentId not in session_roster(implementation,db,row): raise HTTPException(404,'学生不在课堂名单')
        state=data.setdefault('writingState',dict(revision=0,open=[],feedback={}))
        state.setdefault('attendance',{})[str(b.studentId)]=b.present
        save_state(db,snapshot,data,b.expectedRevision)
        return classroom(sid,u,db)

    @router.post('/teacher/weekend/writing/sessions/{sid}/release')
    def release(sid:int,b:WritingRelease,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        implementation.need(u,'teacher')
        row,snapshot,data=class_context(db,u,sid)
        if row.status!='running': raise HTTPException(409,'请先开始课堂')
        allowed={n['id'] for n in data['writingPackage']['nodes'] if n['status']=='confirmed'}
        if not set(b.nodeIds)<=allowed: raise HTTPException(422,'不能开放未审核节点')
        state=data.setdefault('writingState',dict(revision=0,open=[],feedback={}))
        state['open']=b.nodeIds
        opened=set(state.get('openedRoles',[]))
        opened.update(n['role'] for n in data['writingPackage']['nodes'] if n['id'] in b.nodeIds)
        state['openedRoles']=sorted(opened)
        # A writing task, once opened, stays available for an in-flight photo submission.
        task=next(n for n in data['writingPackage']['nodes'] if n['role']=='task' and n['status']=='confirmed')
        if task['id'] in b.nodeIds:
            state['taskOpened']=True
            gates=implementation.Base.metadata.tables['weekend_open_questions']
            qid=db.scalar(select(written['questions'].c.id).where(written['questions'].c.session_id==sid))
            if qid:
                db.execute(update(gates).where(gates.c.session_id==sid).values(opened_question_ids=json.dumps([f'written:{qid}'])))
        save_state(db,snapshot,data,b.expectedRevision)
        return classroom(sid,u,db)

    @router.post('/teacher/weekend/writing/sessions/{sid}/feedback')
    def feedback(sid:int,b:WritingFeedback,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        implementation.need(u,'teacher')
        row,snapshot,data=class_context(db,u,sid)
        if b.studentId not in session_roster(implementation,db,row): raise HTTPException(404,'学生不在本课堂')
        state=data.setdefault('writingState',dict(revision=0,open=[],feedback={}))
        previous=state['feedback'].get(str(b.studentId),{})
        draft=dict(comment=b.comment,nextStep=b.nextStep,at=datetime.utcnow().isoformat(),by=u.id,
                   completion=completion(db,row,data,b.studentId))
        state['feedback'][str(b.studentId)]=dict(draft=draft,history=previous.get('history',[])+[draft],
            published=previous.get('published',[])+([draft] if b.publish else []))
        save_state(db,snapshot,data,b.expectedRevision)
        return classroom(sid,u,db)

    @router.get('/parent/weekend/writing/students/{student_id}')
    def parent_feedback(student_id:int,u:Any=Depends(current_user),db:Any=Depends(get_db)):
        implementation.need(u,'parent')
        link=implementation.ParentStudent
        student=db.get(implementation.User,student_id)
        if student is None or student.school_id!=u.school_id or not db.scalar(select(link.id).where(
            link.parent_id==u.id,link.student_id==student_id)):
            raise HTTPException(404,'没有找到孩子')
        published=[]
        for snapshot in db.execute(select(frozen).where(frozen.c.school_id==u.school_id,frozen.c.course_type=='writing').order_by(frozen.c.session_id.desc())):
            data=json.loads(snapshot.lesson_json)
            versions=data.get('writingState',{}).get('feedback',{}).get(str(student_id),{}).get('published',[])
            if versions: published.append(dict(sessionId=snapshot.session_id,title=data.get('writingPackage',{}).get('title',''),versions=versions))
        return dict(items=published)

    @router.get('/parent/weekend/writing')
    def parent_linked_students(u:Any=Depends(current_user),db:Any=Depends(get_db)):
        implementation.need(u,'parent')
        link=implementation.ParentStudent
        rows=db.execute(select(link.student_id,implementation.User.name).join(implementation.User,implementation.User.id==link.student_id).where(
            link.parent_id==u.id,implementation.User.school_id==u.school_id)).all()
        return dict(students=[dict(id=r[0],name=r[1]) for r in rows])

    @router.get('/v1/weekend-writing',response_class=HTMLResponse)
    def page(): return writing_page()

    @implementation.app.middleware("http")
    async def writing_embed_headers(request, call_next):
        response = await call_next(request)
        if request.url.path == "/v1/weekend-writing" and request.query_params.get("embed") == "1":
            response.headers["X-Frame-Options"] = "SAMEORIGIN"
            csp = response.headers.get("Content-Security-Policy", "")
            if "frame-ancestors 'none'" in csp:
                response.headers["Content-Security-Policy"] = csp.replace("frame-ancestors 'none'", "frame-ancestors 'self'")
        return response

    implementation.app.include_router(router)
    return router
