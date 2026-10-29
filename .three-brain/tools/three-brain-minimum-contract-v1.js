// Three-Brain minimum review contract (rules layer).
//
// This module defines NO data model of its own. The single canonical wire
// format is the v1 Evidence Packet / Decision Record from
// three-brain-shadow-v1.js (packet hash = `contentHash`, record hash =
// `recordHash`, findings = `claims[]`). Records are always re-canonicalized
// through three-brain-intake-v2.js before any rule is applied, so a record
// is either the canonical record or it is rejected.
//
// Rules carried here:
//   - every claim must cite evidence, and every cited ref must be grounded:
//     a packet ref, a file/line inside the change under review, or a
//     governance document (GOVERNANCE.md, docs/adr/ADR-*.md);
//   - the executor cannot certify its own work;
//   - primary / falsifier / tie_breaker roles;
//   - machine evidence must be green before a change can pass;
//   - 1 -> 2 -> 3 risk escalation; conflict escalates to three;
//   - anything missing, conflicting or unprovable fails closed.
//
// Reviewer independence is DECLARED, not attested: `declaredReviewerId` is a
// self-reported label used only to stop one logical reviewer being counted
// twice. It is not proof that two records came from independent models or
// environments.

import {REVIEWER_ROLES} from './three-brain-shadow-v1.js';
import {canonicalizeExternalBrainDecision} from './three-brain-intake-v2.js';

const ACTIONS=new Set(['read','change','deploy']);
const RISKS=new Set(['low','medium','high','review_required']);
const riskRank=Object.freeze({low:1,medium:2,high:3,review_required:4});
const HEX64=/^[a-f0-9]{64}$/;
const FILE_REF=/^file:([^#\s]+)(?:#(?:L(\d+)(?:-L?(\d+))?|[A-Za-z0-9][A-Za-z0-9_.-]{0,80}))?$/;
const GOVERNANCE_PATH=/^(GOVERNANCE\.md|docs\/adr\/ADR-\d{3}[A-Za-z0-9._-]*\.md)$/;

function packetHex(packet){
  const hex=String(packet?.contentHash||'').replace(/^sha256:/,'');
  if(!HEX64.test(hex))throw new Error('valid canonical evidence packet required');
  return hex;
}

export function packetFileRefPath(packet){return 'three-brain/packets/'+packetHex(packet)+'.json';}

export function packetEvidenceRefs(packet){
  packetHex(packet);
  const refs=new Set(Array.isArray(packet.evidenceRefs)?packet.evidenceRefs:[]);
  for(const run of packet.ciRuns||[])if(run?.runId)refs.add('run:'+run.runId);
  for(const s of packet.statuses||[])if(s?.context)refs.add('status:'+s.context);
  return refs;
}

export function parseFileRef(ref){
  const m=FILE_REF.exec(String(ref||''));
  if(!m)return null;
  const path=m[1];
  if(path.startsWith('/')||path.split('/').some(seg=>seg===''||seg==='.'||seg==='..'))return {path,invalid:true};
  const start=m[2]?Number(m[2]):null;
  const end=m[3]?Number(m[3]):start;
  const anchor=!m[2]&&String(ref).includes('#');
  return {path,start,end,anchor};
}

// changedFiles: paths in `git diff --name-only baseSha headSha`, supplied by
// the caller (the packet hash is not changed to carry them). Without it,
// diff file refs cannot be proven and fail closed.
// fileLineCounts: optional {path: lineCount at headSha} for range checks.
export function validateEvidenceRef({packet,ref,changedFiles,fileLineCounts}={}){
  if(packetEvidenceRefs(packet).has(ref))return {ok:true,kind:'packet'};
  const parsed=parseFileRef(ref);
  if(!parsed)return {ok:false,reason:'unknown-ref'};
  if(parsed.invalid)return {ok:false,reason:'invalid-path'};
  // Heading anchors (#slug) are only meaningful for governance documents; code
  // and other diff files must be cited by line range or bare path.
  if(parsed.anchor&&!GOVERNANCE_PATH.test(parsed.path))return {ok:false,reason:'anchor-only-for-governance-docs'};
  if(parsed.start!=null&&(!(parsed.start>=1)||!(parsed.end>=parsed.start)))return {ok:false,reason:'invalid-line-range'};
  if(parsed.path===packetFileRefPath(packet))return {ok:true,kind:'packet-file'};
  if(GOVERNANCE_PATH.test(parsed.path))return {ok:true,kind:'governance'};
  if(!Array.isArray(changedFiles))return {ok:false,reason:'changed-files-unknown'};
  if(!changedFiles.includes(parsed.path))return {ok:false,reason:'file-not-in-diff'};
  const count=fileLineCounts?.[parsed.path];
  if(parsed.end!=null&&Number.isInteger(count)&&parsed.end>count)return {ok:false,reason:'line-out-of-range'};
  return {ok:true,kind:'diff-file'};
}

export function checkRecordGrounding({packet,record,changedFiles,fileLineCounts}={}){
  const claimsWithoutEvidence=[];
  const ungrounded=[];
  for(const claim of record?.claims||[]){
    const refs=Array.isArray(claim?.evidenceRefs)?claim.evidenceRefs:[];
    if(refs.length===0){claimsWithoutEvidence.push(claim?.id||null);continue;}
    for(const ref of refs){
      const v=validateEvidenceRef({packet,ref,changedFiles,fileLineCounts});
      if(!v.ok)ungrounded.push({claimId:claim.id,ref,reason:v.reason});
    }
  }
  return Object.freeze({ok:claimsWithoutEvidence.length===0&&ungrounded.length===0,claimsWithoutEvidence,ungrounded});
}

export function machineEvidenceState(packet){
  packetHex(packet);
  const runs=packet.ciRuns||[];
  const statuses=packet.statuses||[];
  if(runs.length===0&&statuses.length===0)return'missing';
  if(runs.some(r=>r.conclusion!=='success')||statuses.some(s=>s.state!=='success'))return'failing';
  return'green';
}

export function requiredBrainCountForRisk(risk){
  if(!RISKS.has(risk))throw new Error('invalid risk');
  if(risk==='low')return 1;
  if(risk==='medium')return 2;
  return 3;
}

// Role comes from Freeman's assignment for the slot when provided; a role the
// Brain declared itself is used only when no assignment exists.
export function roleOf(record,roleAssignment={}){
  const assigned=roleAssignment?.[record?.brainId];
  if(assigned)return REVIEWER_ROLES.has(assigned)?assigned:null;
  return REVIEWER_ROLES.has(record?.role)?record.role:null;
}

export function validateCanonicalRecords({evidencePacket,records=[],executorId=null,changedFiles,fileLineCounts}={}){
  const packet=evidencePacket;
  try{packetHex(packet);}catch{return {ok:false,reason:'missing-or-invalid-evidence-packet'};}
  const rows=[];
  const brains=new Set();
  const reviewers=new Set();
  for(const input of Array.isArray(records)?records:[]){
    let row;
    try{row=canonicalizeExternalBrainDecision({evidencePacket:packet,input});}
    catch(err){return {ok:false,reason:'non-canonical-record:'+String(err.message||err),brainId:input?.brainId||null};}
    if(brains.has(row.brainId))return {ok:false,reason:'duplicate-brain',brainId:row.brainId};
    brains.add(row.brainId);
    const reviewer=row.declaredReviewerId||null;
    if(reviewer){
      if(reviewers.has(reviewer))return {ok:false,reason:'reviewer-not-independent',brainId:row.brainId};
      reviewers.add(reviewer);
      if(executorId&&reviewer===executorId)return {ok:false,reason:'executor-self-certification-denied',brainId:row.brainId};
    }
    if(executorId&&row.brainId===executorId)return {ok:false,reason:'executor-self-certification-denied',brainId:row.brainId};
    const grounding=checkRecordGrounding({packet,record:row,changedFiles,fileLineCounts});
    if(grounding.claimsWithoutEvidence.length)return {ok:false,reason:'claim-without-evidence',brainId:row.brainId,grounding};
    if(grounding.ungrounded.length)return {ok:false,reason:'ungrounded-evidence-ref',brainId:row.brainId,grounding};
    rows.push(row);
  }
  return {ok:true,rows};
}

const maxRisk=rows=>rows.reduce((m,r)=>riskRank[r.risk]>riskRank[m]?r.risk:m,'low');
const hasDecisionConflict=rows=>new Set(rows.map(r=>r.decision)).size>1;
const blocked=(gate,reason,extra={})=>({status:'BLOCKED_FAIL_CLOSED',gate,reason,...extra});

export function evaluateIntentGate({evidencePacket,records=[],requestedAction='read',executorId=null,roleAssignment={},changedFiles,fileLineCounts}={}){
  if(!ACTIONS.has(requestedAction))return blocked('intent','invalid-action');
  const checked=validateCanonicalRecords({evidencePacket,records,executorId,changedFiles,fileLineCounts});
  if(!checked.ok)return blocked('intent',checked.reason,{brainId:checked.brainId||null});
  const primary=checked.rows.find(r=>roleOf(r,roleAssignment)==='primary');
  if(!primary)return blocked('intent','missing-primary-brain');
  if(primary.decision==='reject'||primary.decision==='unresolved'||primary.unresolved?.length)return blocked('intent','primary-not-actionable');
  const required=requiredBrainCountForRisk(primary.risk);
  if(checked.rows.length<required)return {status:'NEEDS_MORE_REVIEW',gate:'intent',reason:'risk-escalation',requiredBrains:required,currentBrains:checked.rows.length};
  return {status:'PASS',gate:'intent',reason:'intent-grounded',requiredBrains:required,currentBrains:checked.rows.length};
}

export function evaluateChangeGate({evidencePacket,records=[],executorId=null,requestedAction='change',roleAssignment={},changedFiles,fileLineCounts}={}){
  if(!['change','deploy'].includes(requestedAction))return blocked('change','change-gate-requires-change-or-deploy');
  const checked=validateCanonicalRecords({evidencePacket,records,executorId,changedFiles,fileLineCounts});
  if(!checked.ok)return blocked('change',checked.reason,{brainId:checked.brainId||null});
  const rows=checked.rows;
  const roles=rows.map(r=>roleOf(r,roleAssignment));
  if(!roles.includes('primary')||!roles.includes('falsifier')){
    return blocked('change','independent-falsifier-required',{requiredBrains:2,currentBrains:rows.length});
  }
  const machine=machineEvidenceState(evidencePacket);
  if(machine==='failing')return blocked('change','machine-evidence-not-green');
  if(machine==='missing')return blocked('change','machine-evidence-missing');
  const conflict=hasDecisionConflict(rows);
  const required=conflict?3:Math.max(2,requiredBrainCountForRisk(maxRisk(rows)));
  if(rows.length<required)return {status:'NEEDS_MORE_REVIEW',gate:'change',reason:conflict?'decision-conflict-escalation':'risk-escalation',requiredBrains:required,currentBrains:rows.length};
  if(conflict)return blocked('change','decision-conflict-unresolved',{requiredBrains:3,currentBrains:rows.length});
  if(rows.some(r=>r.decision==='reject'||r.decision==='unresolved'||r.unresolved?.length))return blocked('change','review-reject-or-unresolved');
  if(required===3&&!roles.includes('tie_breaker'))return blocked('change','third-brain-role-required',{requiredBrains:3,currentBrains:rows.length});
  return {
    status:'PASS',gate:'change',reason:'independent-review-and-machine-evidence-satisfied',
    requiredBrains:required,currentBrains:rows.length,
    evidencePacketHash:evidencePacket.contentHash,
    recordHashes:rows.map(r=>r.recordHash),
    independence:'declared-not-attested'
  };
}

export function minimumThreeBrainContractStatus(){
  return Object.freeze({
    version:2,
    canonicalSchema:'three-brain-shadow-v1',
    canonicalPacketHash:'contentHash',
    canonicalRecordHash:'recordHash',
    ownDataModel:false,
    transportAgnostic:true,
    oauthRequired:false,
    mcpRequired:false,
    claimIsEvidence:false,
    evidenceRefs:['packet','diff-file','governance'],
    executorSelfCertification:false,
    riskEscalation:'1->2->3',
    missingConflictOrInsufficientEvidence:'fail-closed',
    independence:'declared-not-attested',
    attestedReviewerIdentity:null,
    gates:['intent','change']
  });
}
