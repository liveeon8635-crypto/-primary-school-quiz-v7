/* Dev-only DOM simulation, not Safari/WebKit or real-device acceptance. */
const {JSDOM,VirtualConsole}=require(require('path').resolve(process.argv[2], 'jsdom'));
const fs=require('fs'),assert=require('assert'),acorn=require(require('path').resolve(process.argv[2], 'acorn'));
const html=fs.readFileSync(process.argv[3],'utf8');
let errors=[],requests=[];const vc=new VirtualConsole();vc.on('jsdomError',e=>{if(!/CSS|navigation/.test(e.message))errors.push(e.message)});
const dom=new JSDOM(html,{url:'https://example.test/v1',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){
 w.Object.fromEntries=undefined;w.Object.hasOwn=undefined;w.String.prototype.replaceAll=undefined;w.String.prototype.matchAll=undefined;w.Array.prototype.at=undefined;w.Array.prototype.flat=undefined;w.Array.prototype.flatMap=undefined;w.Promise.allSettled=undefined;w.structuredClone=undefined;w.scrollTo=()=>{};
 w.fetch=async(url,options={})=>{requests.push({url,options});let data=[];if(url==='/login'){const b=JSON.parse(options.body);data={token:'test-'+b.username,userID:b.username==='student-a'?101:102,name:b.username,role:'student',grade:3};w.__testUser=data} else if(url==='/session')data=w.__testUser;else if(String(url).includes('/v1/version'))data={build:''};else if(String(url).includes('progress'))data={knowledge:[]};return {ok:true,status:200,json:async()=>data}};
}});
setTimeout(async()=>{try{
 const w=dom.window,d=w.document;
 for(const s of d.scripts)acorn.parse(s.textContent,{ecmaVersion:2019});
 assert(d.querySelector('form'),'first login form rendered');
 let form=d.querySelector('form'),inputs=form.querySelectorAll('input');
 
 for(const input of inputs)if(input.type!=='checkbox')input.value=input.name==='password'?'test-pass':'student-a';
 form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
 await new Promise(r=>setTimeout(r,50));
 assert(requests.some(x=>String(x.url).includes('login')),'login reached existing API');
 assert(w.sessionStorage.getItem('v717Token')==='test-student-a');
 const switcher=Array.from(d.querySelectorAll('button')).find(b=>b.textContent==='切换账号');assert(switcher);switcher.click();assert(!w.sessionStorage.getItem('v717Token'));assert(!w.localStorage.getItem('v717Token'));
 form=d.querySelector('form');for(const i of form.querySelectorAll('input'))if(i.type!=='checkbox')i.value=i.name==='password'?'test-pass':'student-b';form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,50));assert(w.sessionStorage.getItem('v717Token')==='test-student-b');assert(!w.localStorage.getItem('v717Token'));assert(!w.sessionStorage.getItem('v717User').includes('student-a'));
 assert(w.Object.fromEntries([['x',2]]).x===2);
 assert(w.eval("'a.a'.replaceAll('.', '$&x')")==='a.xa');
 assert(w.eval('[1,[2]].flat().at(-1)')===2);
 const settled=await w.Promise.allSettled([w.Promise.resolve(1),w.Promise.reject('x')]);assert(settled[1].status==='rejected');
 const dialog=d.createElement('dialog');dialog.innerHTML='<button>close</button>';d.body.appendChild(dialog);await new Promise(r=>setTimeout(r,0));
 dialog.showModal();assert(dialog.hasAttribute('open'));assert(d.body.style.position==='fixed');dialog.close();assert(!dialog.hasAttribute('open'));assert(d.body.style.position!=='fixed');
 assert.deepEqual(errors,[]);console.log('PASS: all inline scripts parse ES2019; actual login render/submission, A logout/B login storage isolation without modern APIs; shims and dialog scroll unlock');
}catch(e){console.error(e);process.exitCode=1}finally{process.exit(process.exitCode||0)}},100);
