import subprocess
from changying.web.weekend_pages import CONTROL_JS


def test_pending_written_submission_can_be_invited_with_the_correct_question_type():
    script = CONTROL_JS[CONTROL_JS.index('function peerCard('):CONTROL_JS.index('var PART=')]
    node=r'''
const assert=require('node:assert/strict');
function el(tag,attrs,...children){return {tag,attrs:attrs||{},children,appendChild(n){this.children.push(n);return n},set textContent(t){this.text=t;this.children=[]},get textContent(){return this.text||this.attrs.text||''}}}
function all(n){return [n,...n.children.flatMap(all)]}
var SID=7,sent=[];
function api(path,opts){
 if(path.endsWith('/peer-suggest'))return Promise.resolve({message:'文字／照片题已收到提交',questions:[{questionType:'written',questionId:11,no:1,stem:'概括故事',right:[],wrong:[],submitted:[{studentId:42,name:'甲同学',result:'pending',asked:false}]}]});
 sent.push({path,body:opts.json});return Promise.resolve({message:'已邀请'});
}
async function settle(){for(let i=0;i<30;i++)await Promise.resolve()}
''' + script + r'''
(async()=>{
 const root=el('div');peerCard(root);
 all(root).find(n=>n.attrs.text==='查看可以讲的题').attrs.onclick();await settle();
 assert(all(root).some(n=>n.attrs.text&&n.attrs.text.includes('甲同学（待批改）')));
 const invite=all(root).find(n=>n.attrs.text==='请 甲同学 来讲');assert(invite);
 invite.attrs.onclick();await settle();assert.deepEqual(sent,[{path:'/teacher/weekend/sessions/7/explain',body:{tutorId:42,questionId:11,questionType:'written'}}]);
 assert.equal(invite.textContent,'已请 甲同学 讲过');
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-e',node],text=True,capture_output=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
