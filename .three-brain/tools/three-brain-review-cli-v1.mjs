#!/usr/bin/env node
// Deterministic helper for Brains and operators. No network, no model calls.
//
//   node lib/three-brain-review-cli-v1.mjs verify-packet <packet.json>
//   node lib/three-brain-review-cli-v1.mjs make-record <packet.json> <draft.json> <out.json>
//   node lib/three-brain-review-cli-v1.mjs collect <packet.json> <file-or-dir>... [--tier L1|L2|L3]
//        [--roles claude=primary,gpt=falsifier,gemini=tie_breaker] [--executor <id>]
//   (collect reads changed files from `git diff --name-only baseSha headSha`; if git cannot
//    resolve the SHAs, file refs into the diff fail closed.)
//
// draft.json: {brainId, provider, model, decision, risk, claims:[{text,evidenceRefs}], unresolved:[]}
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {createBrainDecisionRecord} from './three-brain-shadow-v1.js';
import {
  loadEvidencePacketFile,
  collectBusDecisionRecords,
  evaluateHeterogeneousQuorum
} from './three-brain-github-bus-v1.js';

const [cmd,...args]=process.argv.slice(2);
const readPacket=p=>loadEvidencePacketFile(fs.readFileSync(p,'utf8'));
const print=v=>process.stdout.write(JSON.stringify(v,null,2)+'\n');

try{
  if(cmd==='verify-packet'){
    const packet=readPacket(args[0]);
    print({ok:true,evidencePacketHash:packet.contentHash,repository:packet.repository,baseSha:packet.baseSha,headSha:packet.headSha});
  }else if(cmd==='make-record'){
    const packet=readPacket(args[0]);
    const draft=JSON.parse(fs.readFileSync(args[1],'utf8'));
    const record=createBrainDecisionRecord({...draft,evidencePacket:packet});
    fs.mkdirSync(path.dirname(args[2]),{recursive:true});
    fs.writeFileSync(args[2],JSON.stringify(record,null,2)+'\n');
    print({ok:true,out:args[2],brainId:record.brainId,evidencePacketHash:record.evidencePacketHash,recordHash:record.recordHash});
  }else if(cmd==='collect'){
    const packet=readPacket(args[0]);
    const opts={};
    const inputs=[];
    for(let i=1;i<args.length;i++){
      if(args[i].startsWith('--')){opts[args[i].slice(2)]=args[i+1];i++;}else inputs.push(args[i]);
    }
    const roleAssignment=Object.fromEntries(String(opts.roles||'').split(',').filter(Boolean).map(x=>x.split('=')));
    let changedFiles;
    try{
      changedFiles=execFileSync('git',['diff','--name-only',packet.baseSha,packet.headSha],{encoding:'utf8',stdio:['ignore','pipe','ignore']})
        .split('\n').filter(Boolean);
    }catch{changedFiles=undefined;}
    const files=inputs.flatMap(p=>fs.statSync(p).isDirectory()
      ?fs.readdirSync(p).filter(f=>f.endsWith('.json')).map(f=>path.join(p,f)):[p]);
    const sources=files.map(f=>({origin:f.endsWith('.md')?'comment':'file',ref:f,text:fs.readFileSync(f,'utf8')}));
    const collected=collectBusDecisionRecords({packet,sources});
    print({
      changedFilesKnown:Array.isArray(changedFiles),
      collected,
      quorum:evaluateHeterogeneousQuorum({packet,records:collected.records,riskTier:opts.tier||'L1',
        roleAssignment,executorId:opts.executor||null,changedFiles})
    });
  }else{
    process.stderr.write('usage: verify-packet | make-record | collect\n');
    process.exit(2);
  }
}catch(err){
  print({ok:false,error:String(err.message||err)});
  process.exit(1);
}
