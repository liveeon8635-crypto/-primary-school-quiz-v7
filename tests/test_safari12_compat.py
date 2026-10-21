"""Real entry-point coverage; no production DB or runtime npm required."""
import json
import os
import subprocess
import sys
from pathlib import Path

from changying.web.safari12 import ASSETS, compatible_html, safari12_agent, script_key, SCRIPTS

IPAD = 'Mozilla/5.0 (iPad; CPU OS 12_5_8 like Mac OS X) AppleWebKit/605.1.15 Version/12.1.2 Mobile/15E148 Safari/604.1'


def isolated(name, tmp_path):
    if os.environ.get('CY_SAFARI_TEST_CHILD'):
        return False
    env = dict(os.environ, CY_SAFARI_TEST_CHILD='1', HOMEWORK_ASSISTANT='1', CLASSROOM_QUICK_LOGIN='1', DATABASE_URL='sqlite:///'+str(tmp_path/'safari.sqlite3'))
    code = "import runpy; m=runpy.run_path('tests/test_safari12_compat.py'); m[%r](None)" % name
    result = subprocess.run([sys.executable, '-c', code], env=env, text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stdout+result.stderr
    return True


def test_all_shipped_routes_have_current_compilation(tmp_path):
    if isolated('test_all_shipped_routes_have_current_compilation', tmp_path): return
    from changying.compat_tools.build_safari12 import collect
    sources, routes = collect()
    manifest = json.loads((ASSETS / 'manifest.json').read_text())
    assert '/v1' in routes and len(routes) >= 20
    assert set(sources) == set(manifest['scripts']), 'Regenerate Safari 12 assets after inline JS changes'
    assert '/v1/homework' in routes and '/join' in routes
    for source in sources.values():
        result = compatible_html('<html><head></head><body><script>'+source+'</script></body></html>')
        assert 'cy-safari12-runtime' in result


def test_actual_entry_cache_and_modern_representation(tmp_path):
    if isolated('test_actual_entry_cache_and_modern_representation', tmp_path): return
    from app import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        modern = client.get('/v1', headers={'User-Agent':'modern-test', 'Accept-Encoding':'identity'})
        old = client.get('/v1', headers={'User-Agent':IPAD, 'Accept-Encoding':'identity'})
        assert old.status_code == modern.status_code == 200
        assert old.headers['x-changying-safari12'] == 'compiled-v1'
        assert 'cy-safari12-runtime' not in modern.text
        assert 'User-Agent' in modern.headers['vary']
        assert old.headers['etag'] != modern.headers['etag']
        assert old.text.index('cy-safari12-runtime') < old.text.index('const PAGE_BUILD')
        assert client.get('/v1', headers={'User-Agent':IPAD, 'If-None-Match':old.headers['etag'], 'Accept-Encoding':'identity'}).status_code == 304
        assert client.get('/v1', headers={'User-Agent':IPAD, 'If-None-Match':modern.headers['etag'], 'Accept-Encoding':'identity'}).status_code == 200
        for path in ['/v1/classroom-board/12345','/v1/classroom-join-code/67890']:
            dynamic = client.get(path, headers={'User-Agent':IPAD})
            assert dynamic.status_code == 200
            assert '__CY_SESSION__' not in dynamic.text
            assert path.rsplit('/',1)[1] in dynamic.text
        gz = client.get('/v1', headers={'User-Agent':IPAD, 'Accept-Encoding':'gzip'})
        assert gz.text == old.text
        Path('/tmp/safari12-rendered.html').write_text(old.text)
        for homework, quick in [('0','0'),('0','1'),('1','0'),('1','1')]:
            os.environ['HOMEWORK_ASSISTANT'] = homework
            os.environ['CLASSROOM_QUICK_LOGIN'] = quick
            assert client.get('/v1', headers={'User-Agent':IPAD}).status_code == 200


def test_agent_and_build_identity():
    assert safari12_agent(IPAD)
    assert not safari12_agent(IPAD.replace('OS 12_5_8','OS 17_0').replace('Version/12.1.2','Version/17.0'))
    assert script_key('const PAGE_BUILD="one";') == script_key('const PAGE_BUILD="two";')


def test_missing_browser_apis_and_login_submitter():
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const listeners={};
function Element(){}
const context=vm.createContext({console, setTimeout, Element, document:{
  addEventListener:(type,fn)=>listeners[type]=fn,
  createElement:()=>({showModal:()=>{}}),
  getElementById:()=>null
}, Blob, crypto:require('crypto').webcrypto});
vm.runInContext(`window=this; window.addEventListener=()=>{};
Object.fromEntries=undefined;Object.hasOwn=undefined;String.prototype.replaceAll=undefined;
String.prototype.matchAll=undefined;Array.prototype.at=undefined;String.prototype.at=undefined;
Array.prototype.flat=undefined;Array.prototype.flatMap=undefined;Promise.allSettled=undefined;
structuredClone=undefined;`,context);
vm.runInContext(fs.readFileSync('changying/web/safari12_assets/runtime.js','utf8'),context);
vm.runInContext(`
if(Object.fromEntries([['x',2]]).x!==2)throw Error('fromEntries');
if('a.a'.replaceAll('.','$&x')!=='a.xa')throw Error('replaceAll literal/replacement');
if([1,[2]].flat().at(-1)!==2)throw Error('flat/at');
if(Array.from('aba'.matchAll(/a/g)).length!==2)throw Error('matchAll');
const a={x:1};a.self=a;const b=structuredClone(a);if(b===a||b.self!==b)throw Error('clone');
Promise.allSettled([Promise.resolve(1),Promise.reject('x')]).then(r=>{if(r[1].status!=='rejected')throw Error('settled')});
`,context);
const element={firstChild:{},removeChild(){this.firstChild=null},appendChild(node){this.node=node}};
Element.prototype.replaceChildren.call(element,{name:'new'});assert.equal(element.node.name,'new');assert.equal(element.firstChild,null);
const button={type:'submit'},form={querySelector:()=>button};button.form=form;
listeners.click({target:{closest:()=>button}});
const event={target:form};listeners.submit(event);assert.equal(event.submitter,button);
assert.equal(form.__cySubmitter,null);
console.log('OK');
'''
    result = subprocess.run(['node','-e',script], text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'OK' in result.stdout


def test_compiled_assets_reject_known_blank_screen_syntax():
    import base64
    import gzip
    manifest = json.loads((ASSETS/'manifest.json').read_text())
    scripts = []
    for key, entry in manifest['scripts'].items():
        if entry['unchanged']: continue
        source = gzip.decompress(base64.b64decode((ASSETS/(key+'.js.gz.b64')).read_bytes())).decode()
        for syntax in ('?.','??','&&=','||='):
            assert syntax not in source, key+' contains unsupported '+syntax
        scripts.append(source)
    result = subprocess.run(['node','-e',"const vm=require('vm'),fs=require('fs');for(const s of JSON.parse(fs.readFileSync(0,'utf8')))new vm.Script(s)"], input=json.dumps(scripts), text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_photo_crop_touch_drag_cancel_and_cleanup():
    from changying.web.homework_assistant_pages import PHOTO_CROP_JS
    harness = r'''
const assert=require('assert');
let overlay,revoked=0,removed=[];
function el(tag,attrs,...children){
 const handlers={};const e={tag,attrs:attrs||{},style:{},children,clientWidth:600,clientHeight:600,
 appendChild(c){this.children.push(c)},addEventListener(k,fn){handlers[k]=fn},
 remove(){this.removed=true},getAttribute(k){return this.attrs[k]},
 closest(){return this.attrs['data-h']?this:null},fire(k,event){handlers[k](event)}};
 if(attrs&&attrs.onclick)e.click=attrs.onclick;
 return e;
}
const window={addEventListener(){},removeEventListener(k){removed.push(k)}};
const URL={createObjectURL:()=> 'blob:test',revokeObjectURL(){revoked++}};
const document={body:{appendChild(e){overlay=e}},createElement(){return {getContext(){return {drawImage(){}}},toBlob(fn){fn({type:'image/jpeg'})}}}};
function Image(){this.naturalWidth=600;this.naturalHeight=600;Object.defineProperty(this,'src',{set:()=>this.onload()})}
(async()=>{
 let result=cropPhoto({});const stage=overlay.children[1],box=stage.children[1],corner=box.children[0];
 const event=(target,x,y)=>({touches:[{target,clientX:x,clientY:y,identifier:1}],preventDefault(){}});
 const before=Number.parseFloat(box.style.left);
 stage.fire('touchstart',event(corner,100,100));stage.fire('touchmove',event(corner,120,120));
 assert(Number.parseFloat(box.style.left)>before,'touch moves crop corner');
 stage.fire('touchcancel',{});const stopped=box.style.left;
 stage.fire('touchmove',event(corner,150,150));assert.equal(box.style.left,stopped);
 overlay.children[2].children[2].click();assert.equal((await result).type,'image/jpeg');
 assert(overlay.removed);assert.equal(revoked,1);assert(removed.includes('resize')&&removed.includes('mousemove'));
 result=cropPhoto({});overlay.children[2].children[0].click();
 try{await result;throw Error('cancel must reject')}catch(e){assert(e.cancelled)}
 assert.equal(revoked,2);console.log('OK');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node','-e',PHOTO_CROP_JS+harness], text=True, capture_output=True, timeout=30)
    assert result.returncode == 0, result.stdout+result.stderr
    assert 'OK' in result.stdout
