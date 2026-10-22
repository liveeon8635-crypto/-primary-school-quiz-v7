"""Two printable Word question sheets, generated without a runtime dependency."""
from __future__ import annotations

import io
import re
import zipfile
from decimal import Decimal
from xml.etree import ElementTree as ET


def paper_points(question):
    """Use an explicit whole-question mark; defaults are paper marks, not ledger points."""
    lines = str(question['stem']).splitlines()
    # A passage can precede a question. Never borrow a sub-question's marks
    # halfway through a passage or add all parenthesized numbers together.
    candidates = [lines[0] if lines else '']
    candidates += [line for line in lines[1:] if re.match(r'^\s*(?:题目|问题|本题|第\s*\d+\s*题|\d+[.．、])', line)]
    for line in candidates:
        found = re.search(r'(?:[（(【]\s*(?:共|满分|本题|每题)?\s*|(?:本题|满分|共)\s*)(\d+(?:\.\d+)?)\s*分\s*(?:[）)】]|$)', line)
        if found:
            value = Decimal(found.group(1))
            if 0 < value <= 10000:
                return format(value.normalize(), 'f')
    return '2' if question['kind'] == 'choice' else '5'


def question_document(material, audience):
    """Editable OOXML with no source files, teacher plan, scripts or external links."""
    if audience not in ('teacher', 'student'):
        raise ValueError('unknown handout audience')
    teacher = audience == 'teacher'
    ns = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
    rel_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    ET.register_namespace('w', ns)
    ET.register_namespace('r', rel_ns)

    def node(parent, name, attrs=None):
        return ET.SubElement(parent, '{'+ns+'}'+name, {'{'+ns+'}'+k:str(v) for k,v in (attrs or {}).items()})

    def paragraph(parent, text='', style=None, keep=False, after=100, before=0):
        p = node(parent, 'p'); props = node(p, 'pPr')
        if style: node(props, 'pStyle', {'val':style})
        if keep: node(props, 'keepNext')
        node(props, 'spacing', {'after':after,'before':before,'line':300,'lineRule':'auto'})
        # Preserve line breaks and literal question content; remove invalid XML controls.
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]', '', str(text))
        for index, line in enumerate(text.split('\n')):
            run = node(p, 'r')
            if index: node(run, 'br')
            t = node(run, 't');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=line
        return p

    document = ET.Element('{'+ns+'}document');body = node(document,'body')
    role = '教师版' if teacher else '学生版'
    paragraph(body, material['title']+' '+role, 'Title', keep=True, after=160)
    total = sum(Decimal(paper_points(q)) for q in material['questions'])
    paragraph(body, '共'+str(len(material['questions']))+'题　满分'+format(total.normalize(),'f')+'分',keep=True)
    if not teacher: paragraph(body,'姓名：____________　日期：____________',after=180)
    last_material = ''
    for number, q in enumerate(material['questions'], 1):
        stem = q['stem']
        if q['kind'] == 'written' and '\n\n' in stem:
            reading, prompt = stem.rsplit('\n\n', 1)
            if reading != last_material:
                paragraph(body, reading, before=140)
            last_material, stem = reading, prompt
        else:
            last_material = ''
        paragraph(body,'第'+str(number)+'题　'+paper_points(q)+'分','Heading1',keep=True,before=160)
        paragraph(body,stem,keep=bool(q.get('options')))
        for index, option in enumerate(q.get('options', [])):
            paragraph(body,chr(65+index)+'. '+str(option),after=50)
        if teacher:
            reminder = q.get('knowledge') or material['lesson'].get('core_target') or '核对题意与作答要求'
            paragraph(body,'考点提醒：'+str(reminder),'TeacherNote',before=80)
            reference = q.get('reference') or '请教师补充参考答案'
            if q['kind'] == 'choice': reference = chr(65+q['selected'])+'. '+reference
            paragraph(body,'答案：'+reference,'TeacherNote')
            if q.get('explanation'): paragraph(body,'解析：'+q['explanation'],'TeacherNote')
        elif q['kind'] != 'choice':
            # Plain white response space, without pre-filled equations or "答".
            paragraph(body,'\n\n',after=80)
    section = node(body,'sectPr')
    if teacher:
        footer_ref = node(section,'footerReference',{'type':'default'})
        footer_ref.set('{'+rel_ns+'}id','footer')
    node(section,'pgSz',{'w':11906,'h':16838})  # A4, same paper size as the previous printable export.
    node(section,'pgMar',{'top':1020,'right':1020,'bottom':1020,'left':1020,'header':400,'footer':400})

    styles = ET.Element('{'+ns+'}styles')
    defaults = node(styles,'docDefaults');run_props = node(node(defaults,'rPrDefault'),'rPr')
    node(run_props,'rFonts',{'ascii':'Arial','hAnsi':'Arial','eastAsia':'宋体'})
    node(run_props,'sz',{'val':24});node(run_props,'color',{'val':'000000'})
    node(run_props,'lang',{'val':'zh-CN','eastAsia':'zh-CN'})
    for sid, size, bold in [('Normal',24,False),('Title',32,True),('Heading1',24,True),('TeacherNote',22,False)]:
        style = node(styles,'style',{'type':'paragraph','styleId':sid})
        if sid == 'Normal': style.set('{'+ns+'}default','1')
        node(style,'name',{'val':sid});node(style,'basedOn',{'val':'Normal'}) if sid != 'Normal' else None
        props = node(style,'rPr');node(props,'sz',{'val':size});node(props,'color',{'val':'000000'})
        if bold: node(props,'b')
    footer = ET.Element('{'+ns+'}ftr')
    if teacher:
        # The only operational metadata needed to match the paper to the original class.
        paragraph(footer,'原课堂 '+str(material['sessionId'])+'　版本 '+material['version'],'TeacherNote',after=0)

    def xml(element):
        return ET.tostring(element,encoding='utf-8',xml_declaration=True)

    types = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        + ('<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>' if teacher else '')+'</Types>')
    root_rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="document" Type="'+rel_ns+'/officeDocument" Target="word/document.xml"/></Relationships>'
    doc_rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="styles" Type="'+rel_ns+'/styles" Target="styles.xml"/>'
    if teacher: doc_rels += '<Relationship Id="footer" Type="'+rel_ns+'/footer" Target="footer1.xml"/>'
    doc_rels += '</Relationships>'
    out = io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as package:
        package.writestr('[Content_Types].xml',types)
        package.writestr('_rels/.rels',root_rels)
        package.writestr('word/document.xml',xml(document))
        package.writestr('word/styles.xml',xml(styles))
        package.writestr('word/_rels/document.xml.rels',doc_rels)
        if teacher: package.writestr('word/footer1.xml',xml(footer))
    return out.getvalue()
