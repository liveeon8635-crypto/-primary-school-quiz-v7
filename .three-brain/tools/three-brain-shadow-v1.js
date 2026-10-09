import crypto from 'node:crypto';

const SHA40=/^[a-f0-9]{40}$/i;
const BRAIN_IDS=Object.freeze(['gpt','gemini','claude']);
export const THREE_BRAIN_EXECUTION_MODE='app_connector';
export const THREE_BRAIN_API_INVOCATION='forbidden';
const DECISIONS=new Set(['accept','accept_with_changes','reject','unresolved']);
const RISKS=new Set(['low','medium','high','review_required']);
export const REVIEWER_ROLES=new Set(['primary','falsifier','tie_breaker']);

const clean=(v,max=1200)=>String(v??'').replace(/[\r\n\t]+/g,' ').replace(/\s+/g,' ').trim().slice(0,max);
const sha40=v=>{
  const x=String(v||'').trim().toLowerCase();
  if(!SHA40.test(x))throw new Error('invalid sha');
  return x;
};
const stable=v=>{
  if(Array.isArray(v))return v.map(stable);
  if(v&&typeof v==='object'){
    return Object.fromEntries(Object.keys(v).sort().map(k=>[k,stable(v[k])]));
  }
  return v;
};
const hash=v=>'sha256:'+crypto.createHash('sha256').update(JSON.stringify(stable(v))).digest('hex');

export function createEvidencePacket({
  repository,
  baseBranch=null,
  prNumber=null,
  baseSha,
  headSha,
  ciRuns=[],
  statuses=[],
  productionCommit=null,
  evidenceRefs=[],
  policyVersion,
  taskContractHash
}={}){
  const repo=clean(repository,240);
  if(!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo))throw new Error('invalid repository');
  const packet={
    schemaVersion:1,
    repository:repo,
    baseBranch:baseBranch?clean(baseBranch,120):null,
    prNumber:Number.isInteger(Number(prNumber))?Number(prNumber):null,
    baseSha:sha40(baseSha),
    headSha:sha40(headSha),
    ciRuns:(Array.isArray(ciRuns)?ciRuns:[]).slice(0,50).map(row=>({
      name:clean(row?.name,160),
      runId:Number(row?.runId||row?.id||0)||null,
      conclusion:clean(row?.conclusion,64)||null,
      headSha:row?.headSha?sha40(row.headSha):null
    })),
    statuses:(Array.isArray(statuses)?statuses:[]).slice(0,50).map(row=>({
      context:clean(row?.context,160),
      state:clean(row?.state,64)
    })),
    productionCommit:productionCommit?sha40(productionCommit):null,
    evidenceRefs:(Array.isArray(evidenceRefs)?evidenceRefs:[]).slice(0,100).map(x=>clean(x,240)).filter(Boolean),
    policyVersion:clean(policyVersion,120),
    taskContractHash:clean(taskContractHash,200)
  };
  if(!packet.policyVersion)throw new Error('policy version required');
  if(!packet.taskContractHash)throw new Error('task contract hash required');
  return Object.freeze({...packet,contentHash:hash(packet)});
}

export function createBrainDecisionRecord({
  brainId,
  provider,
  model,
  evidencePacket,
  decision,
  risk,
  claims=[],
  unresolved=[],
  declaredReviewerId,
  role,
  transport
}={}){
  if(!BRAIN_IDS.includes(brainId))throw new Error('unsupported brain');
  if(role!=null&&role!==''&&!REVIEWER_ROLES.has(role))throw new Error('invalid reviewer role');
  if(!evidencePacket?.contentHash||!String(evidencePacket.contentHash).startsWith('sha256:'))throw new Error('evidence packet required');
  if(!DECISIONS.has(decision))throw new Error('invalid decision');
  if(!RISKS.has(risk))throw new Error('invalid risk');
  const record={
    schemaVersion:1,
    brainId,
    provider:clean(provider,120),
    model:clean(model,180),
    evidencePacketHash:evidencePacket.contentHash,
    repository:evidencePacket.repository,
    baseSha:evidencePacket.baseSha,
    headSha:evidencePacket.headSha,
    decision,
    risk,
    claims:(Array.isArray(claims)?claims:[]).slice(0,50).map((c,i)=>({
      id:clean(c?.id||`${brainId.toUpperCase()}-${String(i+1).padStart(3,'0')}`,32),
      text:clean(c?.text,1200),
      evidenceRefs:(Array.isArray(c?.evidenceRefs)?c.evidenceRefs:[]).slice(0,20).map(x=>clean(x,240)).filter(Boolean)
    })),
    unresolved:(Array.isArray(unresolved)?unresolved:[]).slice(0,50).map(x=>clean(x,600)).filter(Boolean),
    authority:'read_only',
    writesPerformed:false,
    protectedActions:false
  };
  if(!record.provider||!record.model)throw new Error('provider/model identity required');
  // Optional extension fields enter the record (and its hash) only when
  // present, so records created before they existed keep their recordHash.
  const reviewer=clean(declaredReviewerId,160);
  if(reviewer)record.declaredReviewerId=reviewer;
  if(role)record.role=role;
  const via=clean(transport,80);
  if(via)record.transport=via;
  return Object.freeze({...record,recordHash:hash(record)});
}

export function buildBrainShadowEnvelope({brainId,evidencePacket,goal=''}={}){
  if(!BRAIN_IDS.includes(brainId))throw new Error('unsupported brain');
  if(!evidencePacket?.contentHash)throw new Error('evidence packet required');
  return Object.freeze({
    schemaVersion:1,
    brainId,
    mode:'read-only-shadow',
    executionMode:THREE_BRAIN_EXECUTION_MODE,
    apiInvocation:THREE_BRAIN_API_INVOCATION,
    authority:'read_only',
    goal:clean(goal,1600),
    evidencePacketHash:evidencePacket.contentHash,
    repository:evidencePacket.repository,
    baseSha:evidencePacket.baseSha,
    headSha:evidencePacket.headSha,
    ciRuns:evidencePacket.ciRuns,
    statuses:evidencePacket.statuses,
    productionCommit:evidencePacket.productionCommit,
    evidenceRefs:evidencePacket.evidenceRefs,
    directWrites:false,
    protectedActions:false,
    appConnectorOnly:true,
    apiProviderInvocation:false,
    credentialsIncluded:false,
    rawSecretsIncluded:false
  });
}

export function decisionRecordStorageKey(record){
  if(!record?.recordHash||!BRAIN_IDS.includes(record.brainId))throw new Error('valid decision record required');
  const packetHash=String(record.evidencePacketHash||'').replace(/^sha256:/,'');
  if(!/^[a-f0-9]{64}$/.test(packetHash))throw new Error('invalid evidence packet hash');
  return '__three_brain_decision__:'+packetHash+':'+record.brainId;
}

export async function persistBrainDecisionRecord({store,record,updatedAt=new Date().toISOString()}={}){
  if(!store||store.durable!==true||store.shared!==true||typeof store.claimProjectContextOnce!=='function'){
    throw new Error('durable shared atomic store required');
  }
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
  return Object.freeze({
    persisted:claimed?.claimed===true,
    duplicate:claimed?.claimed!==true,
    projectId,
    recordHash:record.recordHash
  });
}

export function evaluateThreeBrainShadow({evidencePacket,records=[]}={}){
  if(!evidencePacket?.contentHash)throw new Error('evidence packet required');
  const rows=Array.isArray(records)?records:[];
  const byBrain=new Map();
  for(const row of rows){
    if(!row||!BRAIN_IDS.includes(row.brainId))continue;
    if(byBrain.has(row.brainId))return{status:'REVIEW_REQUIRED',reason:'duplicate-brain-record',records:rows};
    byBrain.set(row.brainId,row);
  }
  if(byBrain.size!==BRAIN_IDS.length)return{status:'REVIEW_REQUIRED',reason:'missing-brain-record',records:rows};

  for(const id of BRAIN_IDS){
    const row=byBrain.get(id);
    if(row.evidencePacketHash!==evidencePacket.contentHash)return{status:'REVIEW_REQUIRED',reason:'evidence-hash-mismatch',brainId:id,records:rows};
    if(row.repository!==evidencePacket.repository||row.baseSha!==evidencePacket.baseSha||row.headSha!==evidencePacket.headSha){
      return{status:'REVIEW_REQUIRED',reason:'evidence-identity-mismatch',brainId:id,records:rows};
    }
    if(row.authority!=='read_only'||row.writesPerformed!==false||row.protectedActions!==false){
      return{status:'REVIEW_REQUIRED',reason:'brain-authority-violation',brainId:id,records:rows};
    }
    if(['reject','unresolved'].includes(row.decision)||['high','review_required'].includes(row.risk)||row.unresolved?.length){
      return{status:'REVIEW_REQUIRED',reason:'brain-risk-or-unresolved',brainId:id,records:rows};
    }
  }

  const decisions=new Set(rows.map(r=>r.decision));
  if(decisions.size>1)return{status:'REVIEW_REQUIRED',reason:'brain-disagreement',records:rows};
  const risks=new Set(rows.map(r=>r.risk));
  if(risks.size>1)return{status:'REVIEW_REQUIRED',reason:'risk-disagreement',records:rows};

  const decision=rows[0].decision;
  const risk=rows[0].risk;
  if(decision==='accept'&&risk==='low'){
    return{
      status:'SHADOW_ACCEPT_LOW_RISK',
      reason:'unanimous-low-risk-shadow-only',
      executable:false,
      requiresFreemanPolicyReevaluation:true,
      records:rows
    };
  }
  return{status:'REVIEW_REQUIRED',reason:'non-low-risk-shadow-outcome',records:rows};
}

export function threeBrainShadowStatus(){
  return {
    version:'1.0-shadow',
    brains:[...BRAIN_IDS],
    mode:'read-only-shadow',
    executionMode:THREE_BRAIN_EXECUTION_MODE,
    apiInvocation:THREE_BRAIN_API_INVOCATION,
    appConnectorOnly:true,
    apiProviderInvocation:false,
    directWrites:false,
    directMainReleaseWrites:false,
    directProductionMutation:false,
    credentialsShared:false,
    durableDecisionRecordSupported:true,
    disagreementPreserved:true,
    humanApprovalReceiptSubstitute:false
  };
}
