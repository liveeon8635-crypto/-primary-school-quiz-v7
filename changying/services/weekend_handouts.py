"""Two printable Word question sheets, generated without a runtime dependency."""
from __future__ import annotations

import base64
import hashlib
import io
import re
import zipfile
from decimal import Decimal
from xml.etree import ElementTree as ET

from changying.services.weekend_answers import option_text


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


NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'



WP_NS = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
A_NS = 'http://schemas.openxmlformats.org/drawingml/2006/main'
PIC_NS = 'http://schemas.openxmlformats.org/drawingml/2006/picture'


def _jpeg_dimensions(data):
    """Read JPEG dimensions without adding a runtime imaging dependency."""
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    if not data.startswith(b'\\xff\\xd8'):
        return None
    pos = 2
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            pos += 1
            continue
        while pos < len(data) and data[pos] == 0xFF:
            pos += 1
        if pos >= len(data):
            break
        marker = data[pos]
        pos += 1
        if marker == 0xDA:
            break
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if pos + 2 > len(data):
            break
        length = int.from_bytes(data[pos:pos + 2], 'big')
        if length < 2 or pos + length > len(data):
            break
        if marker in sof and length >= 7:
            height = int.from_bytes(data[pos + 3:pos + 5], 'big')
            width = int.from_bytes(data[pos + 5:pos + 7], 'big')
            if width > 0 and height > 0:
                return width, height
        pos += length
    return None


def _figure_image(figure):
    """Decode only validated embedded JPEG data; never put an external image URL in Word."""
    if not isinstance(figure, dict) or figure.get('type') != 'uploaded_image':
        return None
    data_url = str(figure.get('data_url') or '')
    if len(data_url) > 700000:
        return None
    match = re.fullmatch(r'data:image/jpeg;base64,([A-Za-z0-9+/]+={0,2})', data_url)
    if not match:
        return None
    try:
        data = base64.b64decode(match.group(1), validate=True)
    except (ValueError, TypeError):
        return None
    if not data.startswith(b'\\xff\\xd8\\xff') or not data.endswith(b'\\xff\\xd9'):
        return None
    dimensions = _jpeg_dimensions(data)
    if dimensions:
        width, height = dimensions
        cx, cy = width * 9525, height * 9525
        scale = min(1.0, 5669280 / cx, 3840480 / cy)
        cx, cy = max(1, int(cx * scale)), max(1, int(cy * scale))
    else:
        # Keep an image visible even if a nonstandard JPEG omits a readable SOF segment.
        cx, cy = 4572000, 2743200
    return {'data': data, 'alt': str(figure.get('alt') or '题目插图')[:80], 'cx': cx, 'cy': cy}


def _image_paragraph(parent, image, drawing_id):
    """Add a centered, aspect-preserving DrawingML picture paragraph."""
    p = _node(parent, 'p')
    props = _node(p, 'pPr')
    _node(props, 'jc', {'val': 'center'})
    _node(props, 'spacing', {'after': 100, 'before': 40})
    run = _node(p, 'r')
    drawing = _node(run, 'drawing')
    inline = ET.SubElement(drawing, '{' + WP_NS + '}inline',
                           {'distT': '0', 'distB': '0', 'distL': '0', 'distR': '0'})
    ET.SubElement(inline, '{' + WP_NS + '}extent', {'cx': str(image['cx']), 'cy': str(image['cy'])})
    ET.SubElement(inline, '{' + WP_NS + '}effectExtent', {'l': '0', 't': '0', 'r': '0', 'b': '0'})
    ET.SubElement(inline, '{' + WP_NS + '}docPr',
                  {'id': str(drawing_id), 'name': image['filename'], 'descr': image['alt']})
    frame = ET.SubElement(inline, '{' + WP_NS + '}cNvGraphicFramePr')
    ET.SubElement(frame, '{' + A_NS + '}graphicFrameLocks', {'noChangeAspect': '1'})
    graphic = ET.SubElement(inline, '{' + A_NS + '}graphic')
    graphic_data = ET.SubElement(graphic, '{' + A_NS + '}graphicData', {'uri': PIC_NS})
    picture = ET.SubElement(graphic_data, '{' + PIC_NS + '}pic')
    non_visual = ET.SubElement(picture, '{' + PIC_NS + '}nvPicPr')
    ET.SubElement(non_visual, '{' + PIC_NS + '}cNvPr',
                  {'id': str(drawing_id), 'name': image['filename'], 'descr': image['alt']})
    picture_props = ET.SubElement(non_visual, '{' + PIC_NS + '}cNvPicPr')
    ET.SubElement(picture_props, '{' + A_NS + '}picLocks', {'noChangeAspect': '1'})
    fill = ET.SubElement(picture, '{' + PIC_NS + '}blipFill')
    ET.SubElement(fill, '{' + A_NS + '}blip', {'{' + REL_NS + '}embed': image['rid']})
    stretch = ET.SubElement(fill, '{' + A_NS + '}stretch')
    ET.SubElement(stretch, '{' + A_NS + '}fillRect')
    shape = ET.SubElement(picture, '{' + PIC_NS + '}spPr')
    transform = ET.SubElement(shape, '{' + A_NS + '}xfrm')
    ET.SubElement(transform, '{' + A_NS + '}off', {'x': '0', 'y': '0'})
    ET.SubElement(transform, '{' + A_NS + '}ext', {'cx': str(image['cx']), 'cy': str(image['cy'])})
    geometry = ET.SubElement(shape, '{' + A_NS + '}prstGeom', {'prst': 'rect'})
    ET.SubElement(geometry, '{' + A_NS + '}avLst')
    return p


def _node(parent, name, attrs=None):
    return ET.SubElement(parent, '{'+NS+'}'+name, {'{'+NS+'}'+k:str(v) for k,v in (attrs or {}).items()})


def _paragraph(parent, text='', style=None, keep=False, after=100, before=0):
    p = _node(parent, 'p'); props = _node(p, 'pPr')
    if style: _node(props, 'pStyle', {'val':style})
    if keep: _node(props, 'keepNext')
    _node(props, 'spacing', {'after':after,'before':before,'line':300,'lineRule':'auto'})
    # Preserve line breaks and literal question content; remove invalid XML controls.
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]', '', str(text))
    for index, line in enumerate(text.split('\n')):
        run = _node(p, 'r')
        if index: _node(run, 'br')
        t = _node(run, 't');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=line
    return p


def _a4(body, footer=False):
    section = _node(body,'sectPr')
    if footer:
        footer_ref = _node(section,'footerReference',{'type':'default'})
        footer_ref.set('{'+REL_NS+'}id','footer')
    _node(section,'pgSz',{'w':11906,'h':16838})  # A4, same paper size as the previous printable export.
    _node(section,'pgMar',{'top':1020,'right':1020,'bottom':1020,'left':1020,'header':400,'footer':400})


def _package(document, footer=None, images=None):
    """Zip one body, styles, optional footer and embedded local JPEGs into a .docx."""
    images = list(images or [])
    for prefix, uri in (('w', NS), ('r', REL_NS), ('wp', WP_NS), ('a', A_NS), ('pic', PIC_NS)):
        ET.register_namespace(prefix, uri)
    styles = ET.Element('{' + NS + '}styles')
    defaults = _node(styles, 'docDefaults')
    run_props = _node(_node(defaults, 'rPrDefault'), 'rPr')
    _node(run_props, 'rFonts', {'ascii': 'Arial', 'hAnsi': 'Arial', 'eastAsia': '宋体'})
    _node(run_props, 'sz', {'val': 24})
    _node(run_props, 'color', {'val': '000000'})
    _node(run_props, 'lang', {'val': 'zh-CN', 'eastAsia': 'zh-CN'})
    for sid, size, bold in [('Normal', 24, False), ('Title', 32, True), ('Heading1', 24, True), ('TeacherNote', 22, False)]:
        style = _node(styles, 'style', {'type': 'paragraph', 'styleId': sid})
        if sid == 'Normal':
            style.set('{' + NS + '}default', '1')
        _node(style, 'name', {'val': sid})
        if sid != 'Normal':
            _node(style, 'basedOn', {'val': 'Normal'})
        props = _node(style, 'rPr')
        _node(props, 'sz', {'val': size})
        _node(props, 'color', {'val': '000000'})
        if bold:
            _node(props, 'b')

    def xml(element):
        return ET.tostring(element, encoding='utf-8', xml_declaration=True)

    has_footer = footer is not None
    image_type = '<Default Extension="jpg" ContentType="image/jpeg"/>' if images else ''
    types = ('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + image_type +
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        + ('<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>' if has_footer else '') + '</Types>')
    root_rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="document" Type="' + REL_NS + '/officeDocument" Target="word/document.xml"/></Relationships>')
    doc_rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="styles" Type="' + REL_NS + '/styles" Target="styles.xml"/>')
    if has_footer:
        doc_rels += '<Relationship Id="footer" Type="' + REL_NS + '/footer" Target="footer1.xml"/>'
    for image in images:
        doc_rels += ('<Relationship Id="' + image['rid'] + '" Type="' + REL_NS +
                     '/image" Target="media/' + image['filename'] + '"/>')
    doc_rels += '</Relationships>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as package:
        package.writestr('[Content_Types].xml', types)
        package.writestr('_rels/.rels', root_rels)
        package.writestr('word/document.xml', xml(document))
        package.writestr('word/styles.xml', xml(styles))
        package.writestr('word/_rels/document.xml.rels', doc_rels)
        if has_footer:
            package.writestr('word/footer1.xml', xml(footer))
        for image in images:
            package.writestr('word/media/' + image['filename'], image['data'])
    return out.getvalue()


def question_document(material, audience):
    """Editable OOXML with no source files, teacher plan, scripts or external links."""
    if audience not in ('teacher', 'student'):
        raise ValueError('unknown handout audience')
    teacher = audience == 'teacher'
    paragraph = _paragraph
    document = ET.Element('{'+NS+'}document');body = _node(document,'body')
    role = '教师版' if teacher else '学生版'
    paragraph(body, material['title']+' '+role, 'Title', keep=True, after=160)
    total = sum(Decimal(paper_points(q)) for q in material['questions'])
    paragraph(body, '共'+str(len(material['questions']))+'题　满分'+format(total.normalize(),'f')+'分',keep=True)
    if not teacher: paragraph(body,'姓名：____________　日期：____________',after=180)
    images = []
    image_by_hash = {}
    drawing_count = 0

    def add_question_image(figure):
        nonlocal drawing_count
        image = _figure_image(figure)
        if image is None:
            return
        digest = hashlib.sha256(image['data']).hexdigest()
        if digest not in image_by_hash:
            index = len(images) + 1
            image['rid'] = 'rIdImage' + str(index)
            image['filename'] = 'image' + str(index) + '.jpg'
            images.append(image)
            image_by_hash[digest] = image
        drawing_count += 1
        _image_paragraph(body, image_by_hash[digest], drawing_count)

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
        add_question_image(q.get('figure'))
        for index, option in enumerate(q.get('options', [])):
            paragraph(body,chr(65+index)+'. '+option_text(option),after=50)
        if teacher:
            reminder = q.get('knowledge') or material['lesson'].get('core_target') or '核对题意与作答要求'
            paragraph(body,'考点提醒：'+str(reminder),'TeacherNote',before=80)
            reference = q.get('reference') or '请教师补充参考答案'
            if q['kind'] == 'choice': reference = chr(65+q['selected'])+'. '+option_text(reference)
            paragraph(body,'答案：'+reference,'TeacherNote')
            if q.get('explanation'): paragraph(body,'解析：'+q['explanation'],'TeacherNote')
        elif q['kind'] != 'choice':
            # Plain white response space, without pre-filled equations or "答".
            paragraph(body,'\n\n',after=80)
    _a4(body, footer=teacher)
    footer = None
    if teacher:
        # The only operational metadata needed to match the paper to the original class.
        footer = ET.Element('{'+NS+'}ftr')
        paragraph(footer,'原课堂 '+str(material['sessionId'])+'　版本 '+material['version'],'TeacherNote',after=0)
    return _package(document, footer, images)


def report_document(report):
    """One pupil's learning report: the same text and counts the teacher previewed, nothing about classmates."""
    document = ET.Element('{'+NS+'}document');body = _node(document,'body')
    _paragraph(body, report['studentName']+' 周末课学情反馈', 'Title', keep=True, after=120)
    _paragraph(body, report['date']+'　'+'、'.join(p['subject'] for p in report['facts'])+('　'+report['stateLabel'] if report.get('stateLabel') else ''), after=160)
    for facts, section in zip(report['facts'], report['sections']):
        _paragraph(body, facts['subject']+'　《'+facts['lessonTitle']+'》', 'Heading1', keep=True, before=200)
        c = facts['counts']
        _paragraph(body, '应做 '+str(c['total'])+' 题，已提交 '+str(c['submitted'])+' 题，未提交 '+str(c['unsubmitted'])+' 题；正确 '+str(c['correct'])
                   +' 题，部分正确 '+str(c['partial'])+' 题，需订正 '+str(c['revise'])+' 题，待批改 '+str(c['pending'])+' 题。', 'TeacherNote')
        for key, title in report['titles']:
            if section.get(key):
                _paragraph(body, title, keep=True, before=80, after=40)
                _paragraph(body, section[key])
    if report.get('comment'):
        _paragraph(body, '老师的话', 'Heading1', keep=True, before=200)
        _paragraph(body, report['comment'])
    practice = report.get('practice') or {}
    if practice.get('state') not in (None, 'none'):
        _paragraph(body, '针对性练习（'+str(practice.get('label') or '')+'）', 'Heading1', keep=True, before=200)
        if not practice.get('groups'):
            _paragraph(body, '老师审核后会布置到孩子的“作业”里。')
        for group in practice.get('groups') or []:
            _paragraph(body, str(group.get('subject') or '')+'　'+str(group.get('topic') or ''), keep=True, before=80, after=40)
            for number, q in enumerate(group.get('questions') or [], 1):
                # Question text only: answers and explanations follow the homework's own release rules.
                _paragraph(body, str(number)+'. '+str(q.get('text') or ''), keep=bool(q.get('options')))
                for index, option in enumerate(q.get('options') or []):
                    _paragraph(body, chr(65+index)+'. '+str(option), after=40)
    _a4(body)
    return _package(document)
