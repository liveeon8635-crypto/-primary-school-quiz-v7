import crypto from 'node:crypto';
import {
  createBrainDecisionRecord,
  decisionRecordStorageKey,
  evaluateThreeBrainShadow
} from './three-brain-shadow-v1.js';

const BRAIN_IDS=Object.freeze(['gpt','gemini','claude']);
const stable=v=>Array.isArray(v)?v.map(stable):(v&&typeof v==='object'
  ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]))
  :v);
const hash=v=>'sha256:'+crypto.createHash('sha256').update(JSON.stringify(stable(v))).digest('hex');
const packetHex=packet=>String(packet?.contentHash||'').replace(/^sha256:/,'');

function requirePacket(packet){
  if(!/^[a-f0-9]{64}$/.test(packetHex(packet)))throw new Error('valid evidence packet required');
  return packet;
}

export function canonicalizeExternalBrainDecision({evidencePacket,input}={}){
  const packet=requirePacket(evidencePacket);
  if(!input||typeof input!=='object')throw new Error('decision record required');
  if(!BRAIN_IDS.includes(input.brainId))throw new Error('unsupported brain');
  if(input.evidencePacketHash!==packet.contentHash)throw new Error('evidence hash mismatch');
  if(input.repository!==packet.repository||input.baseSha!==packet.baseSha||input.headSha!==packet.headSha){
    throw new Error('evidence identity mismatch');
  }
  if(input.authority!=='read_only'||input.writesPerformed!==false||input.protectedActions!==false){
    throw new Error('brain authority violation');
  }
  const record=createBrainDecisionRecord({
    brainId:input.brainId,
    provider:input.provider,
    model:input.model,
    evidencePacket:packet,
    decision:input.decision,
    risk:input.risk,
    claims:input.claims,
    unresolved:input.unresolved,
    declaredReviewerId:input.declaredReviewerId,
    role:input.role,
    transport:input.transport
  });
  if(input.recordHash&&input.recordHash!==record.recordHash)throw new Error('record hash mismatch');
  return record;
}

export async function persistExternalBrainDecision({store,evidencePacket,input,updatedAt=new Date().toISOString()}={}){
  if(!store||store.durable!==true||store.shared!==true||
    typeof store.claimProjectContextOnce!=='function'||typeof store.loadProjectContext!=='function'){
    throw new Error('durable shared atomic store required');
  }
  const record=canonicalizeExternalBrainDecision({evidencePacket,input});
  const projectId=decisionRecordStorageKey(record);
  const context={
    schemaVersion:1,
    kind:'three-brain-decision-record',
    record,
    immutable:true,
    authority:'read_only',
    writesPerformed:false,
    protectedActions:false
  };
  const claimed=await store.claimProjectContextOnce({projectId,context,updatedAt});
  if(claimed?.claimed===true){
    return Object.freeze({persisted:true,duplicate:false,projectId,recordHash:record.recordHash});
  }
  const existing=await store.loadProjectContext(projectId);
  const existingHash=existing?.context?.record?.recordHash||null;
  if(existingHash===record.recordHash){
    return Object.freeze({persisted:false,duplicate:true,projectId,recordHash:record.recordHash,idempotent:true});
  }
  throw new Error('conflicting immutable decision record');
}

export async function loadPersistedBrainDecisions({store,evidencePacket}={}){
  if(!store||typeof store.loadProjectContext!=='function')throw new Error('decision store unavailable');
  const packet=requirePacket(evidencePacket);
  const hex=packetHex(packet);
  const rows=[];
  for(const brainId of BRAIN_IDS){
    const projectId='__three_brain_decision__:'+hex+':'+brainId;
    const row=await store.loadProjectContext(projectId);
    if(!row?.context?.record)continue;
    rows.push(canonicalizeExternalBrainDecision({evidencePacket:packet,input:row.context.record}));
  }
  return Object.freeze(rows);
}

const aggregateStorageKey=packet=>'__three_brain_aggregate__:'+packetHex(packet);

export function buildThreeBrainAggregateReceipt({evidencePacket,records}={}){
  const packet=requirePacket(evidencePacket);
  const canonical=(Array.isArray(records)?records:[]).map(input=>
    canonicalizeExternalBrainDecision({evidencePacket:packet,input})
  );
  const evaluation=evaluateThreeBrainShadow({evidencePacket:packet,records:canonical});
  const body={
    schemaVersion:1,
    kind:'three-brain-aggregate-receipt',
    evidencePacketHash:packet.contentHash,
    repository:packet.repository,
    baseSha:packet.baseSha,
    headSha:packet.headSha,
    recordHashes:Object.fromEntries(canonical.map(r=>[r.brainId,r.recordHash])),
    evaluation:{
      status:evaluation.status,
      reason:evaluation.reason,
      executable:evaluation.executable===true,
      requiresFreemanPolicyReevaluation:evaluation.requiresFreemanPolicyReevaluation===true
    },
    authority:'read_only',
    writesPerformed:false,
    protectedActions:false
  };
  return Object.freeze({...body,receiptHash:hash(body)});
}

export async function persistThreeBrainAggregateReceipt({store,evidencePacket,records,updatedAt=new Date().toISOString()}={}){
  if(!store||store.durable!==true||store.shared!==true||
    typeof store.claimProjectContextOnce!=='function'||typeof store.loadProjectContext!=='function'){
    throw new Error('durable shared atomic store required');
  }
  const receipt=buildThreeBrainAggregateReceipt({evidencePacket,records});
  const projectId=aggregateStorageKey(evidencePacket);
  const context={schemaVersion:1,kind:'three-brain-aggregate-receipt',receipt,immutable:true};
  const claimed=await store.claimProjectContextOnce({projectId,context,updatedAt});
  if(claimed?.claimed===true)return Object.freeze({persisted:true,duplicate:false,projectId,receipt});
  const existing=await store.loadProjectContext(projectId);
  if(existing?.context?.receipt?.receiptHash===receipt.receiptHash){
    return Object.freeze({persisted:false,duplicate:true,idempotent:true,projectId,receipt});
  }
  throw new Error('conflicting immutable aggregate receipt');
}

export function buildFreemanDecisionIntake({evidencePacket,aggregateReceipt}={}){
  const packet=requirePacket(evidencePacket);
  if(!aggregateReceipt||aggregateReceipt.evidencePacketHash!==packet.contentHash)throw new Error('aggregate receipt mismatch');
  const {receiptHash,...receiptBody}=aggregateReceipt;
  if(!receiptHash||receiptHash!==hash(receiptBody))throw new Error('aggregate receipt hash mismatch');
  if(aggregateReceipt.repository!==packet.repository||
    aggregateReceipt.baseSha!==packet.baseSha||
    aggregateReceipt.headSha!==packet.headSha||
    aggregateReceipt.authority!=='read_only'||
    aggregateReceipt.writesPerformed!==false||
    aggregateReceipt.protectedActions!==false){
    throw new Error('aggregate receipt identity or authority mismatch');
  }
  const accepted=aggregateReceipt.evaluation?.status==='SHADOW_ACCEPT_LOW_RISK'&&
    aggregateReceipt.evaluation?.executable===false&&
    aggregateReceipt.evaluation?.requiresFreemanPolicyReevaluation===true;
  return Object.freeze({
    schemaVersion:1,
    kind:'three-brain-freeman-intake',
    evidencePacketHash:packet.contentHash,
    repository:packet.repository,
    baseSha:packet.baseSha,
    headSha:packet.headSha,
    aggregateReceiptHash:aggregateReceipt.receiptHash,
    status:accepted?'READY_FOR_FREEMAN_POLICY_REEVALUATION':'REVIEW_REQUIRED',
    executable:false,
    requiresTaskContractReevaluation:true,
    requiresCapabilityFirewallReevaluation:true,
    requiresBrokerPolicyReevaluation:true,
    allowedTools:[],
    directWrites:false,
    directProductionMutation:false,
    humanApprovalReceiptSubstitute:false
  });
}
