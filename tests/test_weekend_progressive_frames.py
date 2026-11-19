import shutil
import subprocess
import pytest
from changying.services import weekend_courseware as cw
from changying.web.weekend_courseware_pages import COURSEWARE_JS


def test_frames_validated_and_preserved():
    f = lambda v: {'type': 'uploaded_image', 'data_url': 'data:image/jpeg;base64,' + v, 'alt': v}
    params = {'steps': ['第一步', '第二步'], 'answer': '30', 'figure': f('QUFB'),
              'stepFigures': [f('QUFB'), f('QkJC'), f('Q0ND')]}
    cleaned = cw.clean_steps(params)
    assert cw.public_params('steps', cleaned)['stepFigures'] == params['stepFigures']
    with pytest.raises(ValueError):
        cw.clean_steps({**params, 'stepFigures': params['stepFigures'][:2]})
    with pytest.raises(ValueError):
        cw.clean_steps({**params, 'stepFigures': [f('QUFB'), {'type':'uploaded_image','data_url':'https://example.com/a'}, f('Q0ND')]})


@pytest.mark.skipif(shutil.which('node') is None, reason='node required')
def test_preview_and_board_render_the_frame_for_each_step():
    harness = r'''
const assert=require('assert');
class E {constructor(tag,a){this.tag=tag;this.a=a||{};this.children=[];this.style='';this.textContent=''}
 appendChild(n){this.children.push(n);return n} setAttribute(k,v){this.a[k]=v}}
function el(tag,a){var n=new E(tag,a);Object.keys(a||{}).forEach(k=>{if(k==='text')n.textContent=a[k];else n.a[k]=a[k]});for(var i=2;i<arguments.length;i++)if(arguments[i])n.appendChild(arguments[i]);return n}
var document={createElement:t=>new E(t),createElementNS:(ns,t)=>new E(t)};
function all(n){return [n].concat(n.children.flatMap(all))}
function draw(step,teacher){var root=new E('div');cwSteps(root,p,{step:step,previewMode:teacher,showAnswer:false},false,teacher);return all(root).filter(n=>n.tag==='img')[0].a.src}
var f=x=>({type:'uploaded_image',data_url:'data:image/jpeg;base64,'+x,alt:x});
var p={title:'例题',steps:['一步','二步'],answer:'答案',figure:f('QUFB'),stepFigures:[f('QUFB'),f('QkJC'),f('Q0ND')]};
assert.strictEqual(cwPreviewFigureTag('steps',{stepFigures:[f('QUFB')]}),'分步图示');
assert.strictEqual(cwPreviewFigureTag('steps',{figure:f('QUFB')}),'原卷图片');
assert.strictEqual(cwPreviewFigureTag('steps',{}),'无图');
for(var teacher of [false,true]){assert(draw(0,teacher).endsWith('QUFB'));assert(draw(1,teacher).endsWith('QkJC'));assert(draw(2,teacher).endsWith('Q0ND'))}
'''
    result = subprocess.run(['node'], input=COURSEWARE_JS + '\n' + harness, capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stderr
