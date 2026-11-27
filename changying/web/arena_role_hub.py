"""三科共享的教师 4 Tab 控制台（热力诊断与派发 / 任务追踪 / 学生明细 / 考点私房题）与家长任务+鼓励视图（纯 ES5，零 DOM 字符串注入）."""
from __future__ import annotations

ARENA_ROLE_HUB_JS = r"""
function arenaRoleHub(role,subject,sess){
  root.textContent='';
  var isTeacher=(role==='teacher'||role==='admin');
  var isInd=!!(sess&&sess.schoolIndividual);
  var backHref=isTeacher?(isInd?'/start':'/v1'):'/classic?legacy=1&unified=1&page=parent';
  var backText=isTeacher?(isInd?'‹ 返回工作室':'‹ 返回工作台'):'‹ 返回家长端';
  var uname=(sess&&sess.name)?String(sess.name):'';
  var subjLinks=el('div',{class:'ea-subj',style:'white-space:nowrap'},
    el('a',{href:'/v1/math-star-map',class:subject==='数学'?'on':'',style:'white-space:nowrap',text:'数学'}),
    el('a',{href:'/v1/english-star-map',class:subject==='英语'?'on':'',style:'white-space:nowrap',text:'英语'}),
    el('a',{href:'/v1/chinese-star-map',class:subject==='语文'?'on':'',style:'white-space:nowrap',text:'语文'}));
  var bar=el('div',{class:'ma-topbar'},
    el('div',{class:'ma-topbar-left'},el('a',{class:'ma-link-btn',href:backHref,style:'white-space:nowrap',text:backText}),subjLinks),
    el('div',{class:'ma-topbar-right'},el('span',{class:'ma-pts',text:isTeacher?((uname?uname+' · ':'')+'教师控制台'):((uname?uname+' · ':'')+'家长学情')})));
  var notice=el('div',{class:'ma-notice'});
  var body=el('div',{class:'ma-wrap'});
  var wrap=el('div',{class:'ma-wrap'},bar,notice,body);
  root.appendChild(wrap);

  function say(t,warn){
    notice.className='ma-notice'+(t?(' show '+(warn?'warn':'info')):'');
    notice.textContent=t||'';
  }
  function helperBar(txt,tag){
    var src=window.__CY_HELPER_AVATAR__||'';
    return el('div',{class:'ma-helper'},
      src?el('img',{class:'ma-helper-ava',src:src,alt:'长缨助手'}):null,
      el('div',{class:'ma-helper-body'},
        el('div',{class:'ma-helper-name',text:tag||'长缨助手'}),
        el('p',{class:'ma-helper-text',text:txt})));
  }
  function defaultDueDate(){
    var dt=new Date();
    dt.setDate(dt.getDate()+2);
    var y=dt.getFullYear();
    var m=dt.getMonth()+1;
    var d=dt.getDate();
    return y+'-'+(m<10?'0'+m:m)+'-'+(d<10?'0'+d:d);
  }
  function hasInList(arr,val){
    if(!arr||!arr.length)return false;
    return arr.indexOf(val)>=0;
  }
  function parseOptionLines(raw){
    var txt=String(raw||'').trim();
    if(!txt)return [];
    var parts=txt.split(/\r?\n/);
    if(parts.length===1&&(txt.indexOf(',')>=0||txt.indexOf('，')>=0)){
      parts=txt.split(/[,，]/);
    }
    var out=[],i,s;
    for(i=0;i<parts.length;i++){
      s=String(parts[i]||'').trim();
      if(s)out.push(s);
    }
    return out;
  }
  function starIcons(n){
    var s='',i,cnt=Number(n)||0;
    for(i=0;i<cnt;i++)s+='★';
    return s;
  }

  /* ================= 教师端 4 Tab 控制台 ================= */
  if(isTeacher){
    var curClassId=0,curTab='heat',diagData=null,taskData=null,customData=null;
    var curDueDate=defaultDueDate();
    var heatStatusFilter='all',heatModuleFilter='all';
    var stuSearchText='';
    var customFilterNode='all';
    var recentFlash={};
    var ctrl=el('div',{class:'ma-card'}),panel=el('div',{class:'ma-wrap'});
    body.appendChild(ctrl);body.appendChild(panel);

    function markLocalDispatched(kind,key){
      if(!diagData)return;
      if(kind==='map_node'){
        if(!diagData.dispatchedNodeKeys)diagData.dispatchedNodeKeys=[];
        if(!hasInList(diagData.dispatchedNodeKeys,key))diagData.dispatchedNodeKeys.push(key);
        if(diagData.nodeHeat){
          diagData.nodeHeat.forEach(function(n){if(n.key===key)n.dispatched=true});
        }
      }else{
        if(!diagData.dispatchedSprintSlugs)diagData.dispatchedSprintSlugs=[];
        if(!hasInList(diagData.dispatchedSprintSlugs,key))diagData.dispatchedSprintSlugs.push(key);
        if(diagData.sprintHeat){
          diagData.sprintHeat.forEach(function(sp){if(sp.slug===key)sp.dispatched=true});
        }
      }
    }

    function dispatchTask(kind,key,goalCode,audience,feedbackEl){
      say('正在派发任务…');
      var payload={
        subject:subject,
        class_id:curClassId,
        task_kind:kind,
        target_key:key,
        goal_code:goalCode,
        audience:audience
      };
      if(curDueDate)payload.due_date=curDueDate;
      api('/teacher/arena/tasks',{
        method:'POST',
        json:payload
      }).then(function(r){
        say('已派发《'+r.targetTitle+'》（'+r.goalLabel+'）给 '+r.assignedCount+' 名学生，截止 '+r.dueDate+'！');
        markLocalDispatched(kind,key);
        var fk=kind+':'+key;
        recentFlash[fk]=true;
        if(feedbackEl){
          feedbackEl.textContent='✓ 已派发';
          feedbackEl.style.display='inline-block';
        }
        loadTasks();
        setTimeout(function(){
          delete recentFlash[fk];
          if(feedbackEl){
            feedbackEl.textContent='';
            feedbackEl.style.display='none';
          }
          refreshDiagnosticsQuiet();
        },1800);
      }).catch(function(e){say(e.message,true)});
    }

    function renderPreviewCard(box,kind,targetKey){
      box.textContent='';
      box.style.display='block';
      box.appendChild(el('p',{class:'ma-sub',style:'margin:0',text:'正在加载题目预览…'}));
      var url='/teacher/arena/preview-questions?subject='+encodeURIComponent(subject)+'&kind='+encodeURIComponent(kind)+'&target_key='+encodeURIComponent(targetKey);
      api(url).then(function(d){
        box.textContent='';
        var items=(d&&d.items)||[];
        var head=el('div',{class:'ma-sum-top',style:'margin-bottom:8px;align-items:center'},
          el('b',{style:'font-size:13.5px',text:(d.targetTitle||targetKey)+' · 题目预览'}),
          el('span',{class:'ma-sub',text:'共 '+items.length+' 题（老师精选 '+(d.customCount||0)+' 题 · 平台自带 '+(d.builtinCount||0)+' 题）'}));
        box.appendChild(head);
        if(!items.length){
          box.appendChild(el('p',{class:'ma-sub',text:'暂无可预览题目。'}));
          return;
        }
        items.forEach(function(q,idx){
          var srcTag=q.isCustom
            ?el('span',{class:'ma-tag mastered',text:'老师精选'})
            :el('span',{class:'ma-pill',text:'平台自带'});
          var qWrap=el('div',{style:'padding:9px 10px;border-radius:10px;background:#fff;border:1px solid #ede4db;margin-top:6px'});
          var metaRow=el('div',{class:'ma-row',style:'gap:6px;margin-bottom:4px'},
            el('span',{class:'ma-node-key',text:'第'+(idx+1)+'题'}),
            srcTag,
            q.typeLabel?el('span',{class:'ma-pill',text:q.typeLabel}):null);
          qWrap.appendChild(metaRow);
          qWrap.appendChild(el('div',{style:'font-size:13.5px;font-weight:700;color:var(--ma-ink);line-height:1.5',text:q.stem||q.text||''}));
          if(q.options&&q.options.length){
            var optRow=el('div',{class:'ma-row',style:'gap:6px;margin-top:5px'});
            q.options.forEach(function(op,oi){
              var letter=String.fromCharCode(65+oi);
              optRow.appendChild(el('span',{class:'ma-pill',text:letter+'. '+op}));
            });
            qWrap.appendChild(optRow);
          }
          qWrap.appendChild(el('div',{class:'ma-sub',style:'margin-top:5px;color:var(--ma-ok);font-weight:700',text:'标准答案：'+(q.answer||'—')}));
          if(q.explanation){
            qWrap.appendChild(el('div',{class:'ma-sub',style:'margin-top:2px',text:'解析：'+q.explanation}));
          }
          box.appendChild(qWrap);
        });
      }).catch(function(e){
        box.textContent='';
        box.appendChild(el('p',{class:'ma-sub',style:'color:var(--ma-brand)',text:'预览加载失败：'+(e.message||'请稍后重试')}));
      });
    }

    function renderCtrl(){
      ctrl.textContent='';
      var sel=el('select',{class:'ma-input',style:'max-width:200px;padding:7px 10px;font-size:13.5px'});
      sel.appendChild(el('option',{value:'0',text:'全部可见学生'}));
      if(diagData&&diagData.classes){
        diagData.classes.forEach(function(c){
          var op=el('option',{value:String(c.id),text:c.name+'（'+c.grade+'年级）'});
          if(Number(c.id)===Number(curClassId))op.selected=true;
          sel.appendChild(op);
        });
      }
      sel.onchange=function(){curClassId=Number(sel.value||0);loadAll()};

      var dueInput=el('input',{type:'date',class:'ma-input',value:curDueDate,style:'width:auto;max-width:155px;padding:6px 9px;font-size:13px'});
      dueInput.value=curDueDate;
      dueInput.onchange=function(){curDueDate=dueInput.value||defaultDueDate()};
      var dueBox=el('label',{class:'ma-row',style:'gap:6px;font-size:13px;font-weight:700;color:var(--ma-muted);white-space:nowrap'},
        el('span',{text:'截止日期'}),
        dueInput);

      var tabs=el('div',{class:'ma-seg',style:'display:inline-flex;flex-wrap:wrap;gap:4px;white-space:nowrap;max-width:100%'});
      [['heat','薄弱热力与派发'],['tasks','任务追踪'],['students','学生明细'],['custom','考点私房题']].forEach(function(t){
        var a=el('a',{href:'#',class:curTab===t[0]?'on':'',style:'white-space:nowrap;flex-shrink:0',text:t[1]});
        a.onclick=function(e){
          e.preventDefault();
          curTab=t[0];
          renderCtrl();
          if(curTab==='custom'&&!customData){loadCustomQuestions()}
          renderPanel();
        };
        tabs.appendChild(a);
      });

      ctrl.appendChild(el('div',{class:'ma-sum-top'},
        el('div',{style:'flex:1 1 240px;min-width:200px'},
          el('div',{class:'ma-eyebrow',text:'教—学—家三端联动 · 小学'+subject}),
          el('h2',{class:'ma-h1',text:subject+'班级诊断与任务派发'}),
          el('p',{class:'ma-sub',text:'覆盖 '+(diagData?diagData.totalNodes:0)+' 个核心考点与 '+(diagData?diagData.totalSprints:0)+' 个限时专项，当前范围 '+(diagData?diagData.studentCount:0)+' 名学生。'})),
        el('div',{class:'ma-row',style:'flex-wrap:wrap;gap:8px;align-items:center'},sel,dueBox)));
      ctrl.appendChild(el('div',{style:'margin-top:12px'},tabs));
    }

    function renderNodeHeatList(listBox){
      listBox.textContent='';
      var allNodes=(diagData&&diagData.nodeHeat)||[];
      var dispatchedNodes=(diagData&&diagData.dispatchedNodeKeys)||[];
      var totalStu=(diagData&&diagData.studentCount)||0;
      var filtered=[];
      allNodes.forEach(function(n){
        var mod=n.module||n.domain||'';
        if(heatModuleFilter!=='all'&&mod!==heatModuleFilter)return;
        if(heatStatusFilter==='weak'){
          if(!((n.weakCount||0)>0||(n.reviewDueCount||0)>0||(n.repairCount||0)>0))return;
        }
        filtered.push(n);
      });
      listBox.appendChild(el('p',{class:'ma-sub',style:'margin-bottom:6px',text:'当前显示 '+filtered.length+' / '+allNodes.length+' 个考点'}));
      if(!filtered.length){
        listBox.appendChild(el('p',{class:'ma-sub',text:'当前筛选条件下暂无匹配考点。'}));
        return;
      }
      filtered.forEach(function(n){
        var unlitCount=Math.max(0,totalStu-(n.litCount||0));
        var isDisp=!!(n.dispatched||hasInList(dispatchedNodes,n.key));
        var mod=n.module||n.domain||'';
        var gSel=el('select',{class:'ma-input',style:'width:auto;padding:5px 8px;font-size:12px'});
        gSel.appendChild(el('option',{value:'lit',text:'目标：点亮'}));
        gSel.appendChild(el('option',{value:'mastered',text:'目标：三星精通'}));
        gSel.appendChild(el('option',{value:'fresh_lit',text:'重刷：新点亮'}));
        gSel.appendChild(el('option',{value:'fresh_mastered',text:'重刷：新三星'}));

        var previewBox=el('div',{style:'display:none;margin:6px 0 8px;padding:10px 12px;border-radius:12px;background:#fcfaf7;border:1px solid #ede4db'});
        var previewOpen=false;
        var bPrev=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'预览题目'});
        bPrev.onclick=function(){
          if(previewOpen){
            previewOpen=false;
            previewBox.style.display='none';
            bPrev.textContent='预览题目';
          }else{
            previewOpen=true;
            bPrev.textContent='收起预览';
            renderPreviewCard(previewBox,'map_node',n.key);
          }
        };

        var fk='map_node:'+n.key;
        var flashSpan=el('span',{class:'ma-tag lit',style:'display:'+(recentFlash[fk]?'inline-block':'none'),text:recentFlash[fk]?'✓ 已派发':''});

        var bWeak=el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'仅派薄弱生('+(n.weakCount||0)+')'});
        bWeak.disabled=((n.weakCount||0)<=0);
        bWeak.onclick=function(){dispatchTask('map_node',n.key,gSel.value,'weak',flashSpan)};
        var bAll=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'派全班'});
        bAll.disabled=(totalStu<=0);
        bAll.onclick=function(){dispatchTask('map_node',n.key,gSel.value,'all',flashSpan)};

        var titleLine=el('div',{class:'ma-row',style:'gap:6px;align-items:center'},
          el('b',{text:n.key+' '+n.name}),
          mod?el('span',{class:'ma-pill',text:mod}):null,
          isDisp?el('span',{class:'ma-tag lit',text:'已派发'}):null);
        var statText='已点亮 '+(n.litCount||0)+'/'+totalStu+'（'+(n.litRate||0)+'%）· 未点亮 '+unlitCount+' · 标红 '+(n.repairCount||0)+' · 待温习 '+(n.reviewDueCount||0);

        var rowWrap=el('div',{style:'border-bottom:1px solid #f1e8df;padding:8px 0'},
          el('div',{class:'ma-loss-row',style:'border-bottom:0;padding:0;flex-wrap:wrap;gap:8px;align-items:center'},
            el('div',{style:'flex:1 1 220px;min-width:200px'},
              titleLine,
              el('div',{class:'ma-sub',style:'margin-top:3px',text:statText})),
            el('div',{class:'ma-row',style:'flex-wrap:wrap;gap:6px;align-items:center'},gSel,bPrev,bWeak,bAll,flashSpan)),
          previewBox);
        listBox.appendChild(rowWrap);
      });
    }

    function renderCustomTab(){
      var allNodes=(diagData&&diagData.nodeHeat)?diagData.nodeHeat.slice():[];
      allNodes.sort(function(a,b){return String(a.key).localeCompare(String(b.key))});
      var nodeNameMap={};
      allNodes.forEach(function(n){nodeNameMap[n.key]=n.name});

      panel.appendChild(helperBar('添加本校专属考点私房题后，学生在对应考点微测时会自动优先抽到老师加的题目（单次最多混入 3 题）！','长缨助手 · 考点私房题'));

      var formCard=el('div',{class:'ma-card'},el('h3',{text:'添加'+subject+'考点私房题'}));
      var nodeSel=el('select',{class:'ma-input',style:'max-width:260px;padding:7px 10px;font-size:13.5px'});
      allNodes.forEach(function(n){
        nodeSel.appendChild(el('option',{value:n.key,text:n.key+' '+n.name}));
      });
      var typeSel=el('select',{class:'ma-input',style:'max-width:160px;padding:7px 10px;font-size:13.5px'});
      typeSel.appendChild(el('option',{value:'single_choice',text:'单选题'}));
      typeSel.appendChild(el('option',{value:'fill_blank',text:'填空题'}));
      typeSel.appendChild(el('option',{value:'true_false',text:'判断题'}));

      var stemInput=el('textarea',{class:'ma-input',rows:'3',placeholder:'请输入题干内容…',style:'max-width:100%;font-size:14px;font-family:inherit'});
      var optInput=el('textarea',{class:'ma-input',rows:'3',placeholder:'每行一个选项，或用逗号分隔（至少 2 个选项）',style:'max-width:100%;font-size:14px;font-family:inherit'});
      var optWrap=el('div',{style:'margin-top:8px'},
        el('div',{class:'ma-sub',style:'margin-bottom:4px;font-weight:700',text:'选项（单选题必填，每行一个或逗号分隔）'}),
        optInput);
      var tfHint=el('p',{class:'ma-sub',style:'display:none;margin-top:6px',text:'判断题默认选项为「正确 / 错误」，标准答案请填写「正确」或「错误」。'});

      var ansInput=el('input',{type:'text',class:'ma-input',placeholder:'填写正确选项内容或 A/B/C/D',style:'max-width:100%;font-size:14px'});
      var expInput=el('textarea',{class:'ma-input',rows:'2',placeholder:'题目解析（选填，学生答错或交卷后展示）',style:'max-width:100%;font-size:14px;font-family:inherit'});

      function syncTypeUi(){
        var tp=typeSel.value;
        if(tp==='single_choice'){
          optWrap.style.display='block';
          tfHint.style.display='none';
          ansInput.placeholder='填写正确选项内容或 A/B/C/D';
        }else if(tp==='true_false'){
          optWrap.style.display='none';
          tfHint.style.display='block';
          ansInput.placeholder='填写 正确 或 错误';
        }else{
          optWrap.style.display='none';
          tfHint.style.display='none';
          ansInput.placeholder='填写标准答案（支持多个等价答案，精确忽略首尾空白与大小写）';
        }
      }
      typeSel.onchange=syncTypeUi;
      syncTypeUi();

      var saveBtn=el('button',{type:'button',class:'ma-btn ma-btn-primary',text:'保存私房题'});
      saveBtn.onclick=function(){
        var nk=nodeSel.value||'';
        var qt=typeSel.value||'single_choice';
        var stem=String(stemInput.value||'').trim();
        var ans=String(ansInput.value||'').trim();
        var exp=String(expInput.value||'').trim();
        var opts=[];
        if(!nk){say('请先选择考点',true);return}
        if(!stem){say('题干不能为空',true);return}
        if(!ans){say('标准答案不能为空',true);return}
        if(qt==='single_choice'){
          opts=parseOptionLines(optInput.value);
          if(opts.length<2){say('单选题至少需要 2 个非空选项',true);return}
        }else if(qt==='true_false'){
          opts=['正确','错误'];
        }
        saveBtn.disabled=true;
        say('正在保存私房题…');
        api('/teacher/arena/custom-questions',{
          method:'POST',
          json:{
            subject:subject,
            node_key:nk,
            question_type:qt,
            stem:stem,
            options:opts,
            answer:ans,
            explanation:exp
          }
        }).then(function(){
          saveBtn.disabled=false;
          stemInput.value='';
          optInput.value='';
          ansInput.value='';
          expInput.value='';
          say('私房题已保存，学生微测该考点时将自动优先抽到！');
          loadCustomQuestions();
        }).catch(function(e){
          saveBtn.disabled=false;
          say(e.message||'保存失败',true);
        });
      };

      formCard.appendChild(el('div',{class:'ma-row',style:'gap:8px;margin-top:8px'},nodeSel,typeSel));
      formCard.appendChild(el('div',{style:'margin-top:8px'},
        el('div',{class:'ma-sub',style:'margin-bottom:4px;font-weight:700',text:'题干'}),
        stemInput));
      formCard.appendChild(optWrap);
      formCard.appendChild(tfHint);
      formCard.appendChild(el('div',{style:'margin-top:8px'},
        el('div',{class:'ma-sub',style:'margin-bottom:4px;font-weight:700',text:'标准答案'}),
        ansInput));
      formCard.appendChild(el('div',{style:'margin-top:8px'},
        el('div',{class:'ma-sub',style:'margin-bottom:4px;font-weight:700',text:'解析（选填）'}),
        expInput));
      formCard.appendChild(el('div',{style:'margin-top:12px'},saveBtn));
      panel.appendChild(formCard);

      var listCard=el('div',{class:'ma-card'});
      var filterSel=el('select',{class:'ma-input',style:'max-width:240px;padding:6px 9px;font-size:13px'});
      filterSel.appendChild(el('option',{value:'all',text:'全部考点'}));
      allNodes.forEach(function(n){
        var op=el('option',{value:n.key,text:n.key+' '+n.name});
        if(n.key===customFilterNode)op.selected=true;
        filterSel.appendChild(op);
      });
      var customListBox=el('div',{style:'margin-top:10px'});

      function paintCustomList(){
        customListBox.textContent='';
        if(!customData){
          customListBox.appendChild(el('p',{class:'ma-sub',text:'正在加载本校私房题…'}));
          return;
        }
        var items=(customData.items||[]).filter(function(q){
          return customFilterNode==='all'||q.nodeKey===customFilterNode;
        });
        if(!items.length){
          customListBox.appendChild(el('p',{class:'ma-sub',text:'当前筛选下暂无私房题，可在上方快速添加。'}));
          return;
        }
        items.forEach(function(q){
          var nTitle=q.nodeKey+(nodeNameMap[q.nodeKey]?(' '+nodeNameMap[q.nodeKey]):'');
          var delBtn=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'删除'});
          delBtn.onclick=function(){
            delBtn.disabled=true;
            api('/teacher/arena/custom-questions/'+q.id,{method:'DELETE'}).then(function(){
              say('已删除私房题');
              loadCustomQuestions();
            }).catch(function(e){
              delBtn.disabled=false;
              say(e.message||'删除失败',true);
            });
          };
          var itemBox=el('div',{style:'padding:10px 12px;border-radius:12px;border:1px solid #ede4db;background:#fcfaf7;margin-bottom:8px'});
          itemBox.appendChild(el('div',{class:'ma-sum-top',style:'align-items:center'},
            el('div',{class:'ma-row',style:'gap:6px'},
              el('span',{class:'ma-node-key',text:nTitle}),
              el('span',{class:'ma-tag mastered',text:q.typeLabel||'老师加题'}),
              q.createdAt?el('span',{class:'ma-sub',text:q.createdAt}):null),
            delBtn));
          itemBox.appendChild(el('div',{style:'margin-top:6px;font-size:14px;font-weight:700;color:var(--ma-ink);line-height:1.5',text:q.stem||q.text||''}));
          if(q.options&&q.options.length){
            var oRow=el('div',{class:'ma-row',style:'gap:6px;margin-top:5px'});
            q.options.forEach(function(op,oi){
              oRow.appendChild(el('span',{class:'ma-pill',text:String.fromCharCode(65+oi)+'. '+op}));
            });
            itemBox.appendChild(oRow);
          }
          itemBox.appendChild(el('div',{class:'ma-sub',style:'margin-top:5px;color:var(--ma-ok);font-weight:700',text:'答案：'+(q.answer||'')}));
          if(q.explanation){
            itemBox.appendChild(el('div',{class:'ma-sub',style:'margin-top:2px',text:'解析：'+q.explanation}));
          }
          customListBox.appendChild(itemBox);
        });
      }

      filterSel.onchange=function(){customFilterNode=filterSel.value||'all';paintCustomList()};
      listCard.appendChild(el('div',{class:'ma-sum-top',style:'align-items:center'},
        el('h3',{style:'margin:0',text:'本校已添加'+subject+'私房题'}),
        filterSel));
      listCard.appendChild(customListBox);
      paintCustomList();
      panel.appendChild(listCard);
    }

    function renderPanel(){
      panel.textContent='';
      if(!diagData){panel.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:'正在加载班级诊断数据…'})));return}

      if(curTab==='heat'){
        panel.appendChild(helperBar('按本班未点亮、标红和待温习人数自动排序：支持筛选模块、预览题目、强制重刷与自定义截止日期，学生达标后系统自动验收！','长缨助手 · 精准分层建议'));

        var modules=[],modSeen={};
        (diagData.nodeHeat||[]).forEach(function(n){
          var m=n.module||n.domain||'';
          if(m&&!modSeen[m]){modSeen[m]=true;modules.push(m)}
        });
        if(heatModuleFilter!=='all'&&!modSeen[heatModuleFilter])heatModuleFilter='all';

        var stSel=el('select',{class:'ma-input',style:'width:auto;max-width:190px;padding:6px 9px;font-size:13px'});
        stSel.appendChild(el('option',{value:'all',text:'全部考点'}));
        stSel.appendChild(el('option',{value:'weak',text:'仅看薄弱或待温习'}));
        stSel.value=heatStatusFilter;

        var modSel=el('select',{class:'ma-input',style:'width:auto;max-width:190px;padding:6px 9px;font-size:13px'});
        modSel.appendChild(el('option',{value:'all',text:'全部知识模块'}));
        modules.forEach(function(m){
          var op=el('option',{value:m,text:'模块：'+m});
          if(m===heatModuleFilter)op.selected=true;
          modSel.appendChild(op);
        });

        var nodeListBox=el('div',{style:'margin-top:8px'});
        stSel.onchange=function(){heatStatusFilter=stSel.value||'all';renderNodeHeatList(nodeListBox)};
        modSel.onchange=function(){heatModuleFilter=modSel.value||'all';renderNodeHeatList(nodeListBox)};

        var nCard=el('div',{class:'ma-card'},
          el('div',{class:'ma-sum-top',style:'align-items:center'},
            el('h3',{style:'margin:0',text:'全班考点薄弱热力榜（全部考点）'}),
            el('div',{class:'ma-row',style:'gap:6px'},stSel,modSel)),
          nodeListBox);
        renderNodeHeatList(nodeListBox);
        panel.appendChild(nCard);

        var sCard=el('div',{class:'ma-card'},el('h3',{text:'应试专项达标率与派发'}));
        var dispatchedSprints=(diagData&&diagData.dispatchedSprintSlugs)||[];
        var totalStu=(diagData&&diagData.studentCount)||0;
        (diagData.sprintHeat||[]).forEach(function(sp){
          var isDisp=!!(sp.dispatched||hasInList(dispatchedSprints,sp.slug));
          var sSel=el('select',{class:'ma-input',style:'width:auto;padding:5px 8px;font-size:12px'});
          sSel.appendChild(el('option',{value:'complete',text:'目标：完成1次'}));
          sSel.appendChild(el('option',{value:'tier_b',text:'目标：B级以上'}));
          sSel.appendChild(el('option',{value:'fresh_complete',text:'重刷：新完成1次'}));
          sSel.appendChild(el('option',{value:'fresh_tier_b',text:'重刷：新冲B级以上'}));

          var previewBox=el('div',{style:'display:none;margin:6px 0 8px;padding:10px 12px;border-radius:12px;background:#fcfaf7;border:1px solid #ede4db'});
          var previewOpen=false;
          var bPrev=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'预览题目'});
          bPrev.onclick=function(){
            if(previewOpen){
              previewOpen=false;
              previewBox.style.display='none';
              bPrev.textContent='预览题目';
            }else{
              previewOpen=true;
              bPrev.textContent='收起预览';
              renderPreviewCard(previewBox,'sprint',sp.slug);
            }
          };

          var fk='sprint:'+sp.slug;
          var flashSpan=el('span',{class:'ma-tag lit',style:'display:'+(recentFlash[fk]?'inline-block':'none'),text:recentFlash[fk]?'✓ 已派发':''});

          var bW=el('button',{type:'button',class:'ma-btn ma-btn-primary ma-btn-sm',text:'仅派未达标('+(sp.weakCount||0)+')'});
          bW.disabled=((sp.weakCount||0)<=0);
          bW.onclick=function(){dispatchTask('sprint',sp.slug,sSel.value,'weak',flashSpan)};
          var bA=el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'派全班'});
          bA.disabled=(totalStu<=0);
          bA.onclick=function(){dispatchTask('sprint',sp.slug,sSel.value,'all',flashSpan)};

          var titleRow=el('div',{class:'ma-row',style:'gap:6px;align-items:center'},
            el('b',{text:sp.title}),
            isDisp?el('span',{class:'ma-tag lit',text:'已派发'}):null);

          sCard.appendChild(el('div',{style:'border-bottom:1px solid #f1e8df;padding:8px 0'},
            el('div',{class:'ma-loss-row',style:'border-bottom:0;padding:0;flex-wrap:wrap;gap:8px;align-items:center'},
              el('div',{style:'flex:1 1 220px;min-width:200px'},
                titleRow,
                el('div',{class:'ma-sub',style:'margin-top:3px',text:'已达标(B级/L2+) '+(sp.passedCount||0)+'/'+totalStu+'（'+(sp.passRate||0)+'%）· 参与 '+(sp.attemptedCount||0)+' 人'})),
              el('div',{class:'ma-row',style:'flex-wrap:wrap;gap:6px;align-items:center'},sSel,bPrev,bW,bA,flashSpan)),
            previewBox));
        });
        panel.appendChild(sCard);
        return;
      }

      if(curTab==='tasks'){
        var list=(taskData&&taskData.items)||[];
        if(!list.length){
          panel.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:'当前还没有派发过'+subject+'任务，去「薄弱热力与派发」一键布置一个吧！'})));
          return;
        }
        list.forEach(function(tk){
          var pct=tk.totalCount?Math.round(tk.doneCount/tk.totalCount*100):0;
          var closeBtn=tk.status==='active'?el('button',{type:'button',class:'ma-btn ma-btn-ghost ma-btn-sm',text:'结束任务',onclick:function(){
            api('/teacher/arena/tasks/'+tk.id+'/close',{method:'POST'}).then(function(){say('已结束任务');loadTasks();refreshDiagnosticsQuiet()}).catch(function(e){say(e.message,true)});
          }}):el('span',{class:'ma-pill',text:'已结束'});
          panel.appendChild(el('div',{class:'ma-card'},
            el('div',{class:'ma-sum-top'},
              el('div',{},
                el('div',{class:'ma-row',style:'gap:6px;align-items:center'},
                  el('b',{text:tk.targetTitle+' · '+tk.goalLabel}),
                  tk.isFresh?el('span',{class:'ma-tag exploring',text:'强制重刷'}):null),
                el('p',{class:'ma-sub',text:tk.audienceLabel+' · 截止 '+tk.dueDate+' · 达标进度 '+tk.doneCount+'/'+tk.totalCount+'（'+pct+'%）'})),
              closeBtn),
            el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'})),
            tk.pendingNames&&tk.pendingNames.length
              ?el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-brand)',text:'待完成学生：'+tk.pendingNames.join('、')})
              :el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-ok);font-weight:700',text:'🎉 全员已自动达标完成！'})));
        });
        return;
      }

      if(curTab==='custom'){
        renderCustomTab();
        return;
      }

      /* Tab 3: 学生明细 */
      var searchInput=el('input',{type:'text',class:'ma-input',placeholder:'输入学生姓名搜索…',value:stuSearchText,style:'max-width:260px;padding:7px 11px;font-size:13.5px'});
      searchInput.value=stuSearchText;
      var stuListBox=el('div',{class:'ma-wrap'});

      function paintStudents(){
        stuListBox.textContent='';
        var kw=String(stuSearchText||'').trim().toLowerCase();
        var allStu=(diagData&&diagData.students)||[];
        var matched=allStu.filter(function(it){
          if(!kw)return true;
          return String(it.name||'').toLowerCase().indexOf(kw)>=0;
        });
        if(!matched.length){
          stuListBox.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:kw?'未找到姓名包含「'+stuSearchText+'」的学生。':'当前班级暂无学生记录。'})));
          return;
        }
        matched.forEach(function(it){
          var pct=it.totalNodes?Math.round(it.litNodes/it.totalNodes*100):0;
          var tierTxt=it.bestTier?(it.bestTier.code+' '+it.bestTier.name):'尚未参加专项';
          var pendCnt=Number(it.pendingTasksCount||0);
          var revCnt=Number(it.reviewDueCount||0);
          stuListBox.appendChild(el('div',{class:'ma-card'},
            el('div',{class:'ma-sum-top'},
              el('div',{},
                el('h3',{style:'margin:0',text:it.name+(it.grade?'（'+it.grade+'年级）':'')}),
                el('p',{class:'ma-sub',style:'margin-top:3px',text:'已点亮 '+it.litNodes+'/'+it.totalNodes+'（'+pct+'%）· 精通 '+it.masteredNodes+' · 专项最高：'+tierTxt})),
              el('span',{class:'ma-pts',text:'全站积分 '+it.pointsBalance})),
            el('div',{class:'ma-row',style:'gap:8px;margin-top:8px'},
              el('span',{class:'ma-tag '+(pendCnt>0?'repair':'lit'),text:'待完成老师任务：'+pendCnt+' 项'}),
              el('span',{class:'ma-tag '+(revCnt>0?'exploring':'unexplored'),text:'待温习考点：'+revCnt+' 个'})),
            el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'})),
            it.repairNames&&it.repairNames.length
              ?el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-brand)',text:'待修补考点：'+it.repairNames.join('、')})
              :el('p',{class:'ma-sub',style:'margin-top:8px',text:'当前无待修补失分点'})));
        });
      }

      searchInput.oninput=function(){stuSearchText=searchInput.value||'';paintStudents()};
      panel.appendChild(el('div',{class:'ma-card'},
        el('div',{class:'ma-sum-top',style:'align-items:center'},
          el('h3',{style:'margin:0',text:'学生个人闯关明细（共 '+((diagData&&diagData.students)?diagData.students.length:0)+' 人）'}),
          searchInput)));
      panel.appendChild(stuListBox);
      paintStudents();
    }

    function loadTasks(){
      api('/teacher/arena/tasks?subject='+encodeURIComponent(subject)+'&class_id='+curClassId).then(function(d){
        taskData=d;if(curTab==='tasks')renderPanel();
      }).catch(function(){});
    }
    function loadCustomQuestions(){
      api('/teacher/arena/custom-questions?subject='+encodeURIComponent(subject)).then(function(d){
        customData=d;if(curTab==='custom')renderPanel();
      }).catch(function(e){say(e.message||'加载私房题失败',true)});
    }
    function refreshDiagnosticsQuiet(){
      api('/teacher/arena/diagnostics?subject='+encodeURIComponent(subject)+'&class_id='+curClassId).then(function(d){
        diagData=d;
        renderCtrl();
        if(curTab==='heat'||curTab==='students')renderPanel();
      }).catch(function(){});
    }
    function loadAll(){
      api('/teacher/arena/diagnostics?subject='+encodeURIComponent(subject)+'&class_id='+curClassId).then(function(d){
        diagData=d;renderCtrl();renderPanel();loadTasks();
      }).catch(function(e){say(e.message,true)});
    }
    loadAll();
    return;
  }

  /* ================= 家长端：老师任务同步 + 三科学情 + 点赞鼓励 ================= */
  function loadParent(){
    api('/parent/arena-summary?subject='+encodeURIComponent(subject)).then(function(d){
      body.textContent='';
      body.appendChild(el('div',{class:'ma-card'},
        el('div',{class:'ma-eyebrow',text:'家校同步 · 小学'+subject}),
        el('h2',{class:'ma-h1',text:'孩子'+subject+'任务进度与闯关学情'}),
        el('p',{class:'ma-sub',text:'实时同步老师布置的地图/专项任务、点亮进度、待温习考点与待修补薄弱点，每天可给孩子点个赞送上鼓励！'})));
      body.appendChild(helperBar('这里自动汇总老师最新布置的练习任务与孩子掌握情况。点「给孩子点赞鼓励」，孩子打开自主练习时我会立刻转达你的鼓励！','长缨助手 · 家校联动'));
      var children=(d&&(d.children||d.items))||[];
      if(!children.length){
        body.appendChild(el('div',{class:'ma-card'},el('p',{class:'ma-sub',text:'暂未关联孩子账号。'})));
        return;
      }
      children.forEach(function(ch){
        var st=(ch.subjects&&ch.subjects[0])||{litNodes:0,totalNodes:16,masteredNodes:0,repairNames:[],bestTier:null,reviewDueCount:0,nodeDetails:[]};
        var pct=st.totalNodes?Math.round(st.litNodes/st.totalNodes*100):0;
        var revDueCnt=(typeof st.reviewDueCount==='number')?st.reviewDueCount:Number(ch.reviewDueCount||0);
        var detailsList=(st.nodeDetails&&st.nodeDetails.length)?st.nodeDetails:(ch.nodeDetails||[]);

        var cheerBtn=el('button',{type:'button',class:'ma-btn '+(ch.cheeredToday?'ma-btn-ghost':'ma-btn-primary')+' ma-btn-sm',text:ch.cheeredToday?'👍 今日已点赞鼓励':'👍 给孩子点赞鼓励'});
        cheerBtn.disabled=!!ch.cheeredToday;
        cheerBtn.onclick=function(){
          api('/parent/arena-cheers',{method:'POST',json:{student_id:ch.studentId,subject:subject,message:'坚持'+subject+'自主练习真棒，继续加油！'}}).then(function(){
            say('已发送鼓励！孩子下次打开自主练习时，长缨助手会立刻转达！');
            loadParent();
          }).catch(function(e){say(e.message,true)});
        };
        var card=el('div',{class:'ma-card'},
          el('div',{class:'ma-sum-top'},
            el('div',{},
              el('h3',{style:'margin:0',text:ch.name+(ch.grade?'（'+ch.grade+'年级）':'')}),
              el('p',{class:'ma-sub',style:'margin-top:3px',text:'已点亮 '+st.litNodes+'/'+st.totalNodes+'（'+pct+'%）· 精通 '+st.masteredNodes+' · 专项最高：'+(st.bestTier?(st.bestTier.code+' '+st.bestTier.name):'尚未参加')})),
            el('div',{class:'ma-row'},el('span',{class:'ma-pts',text:'全站积分 '+ch.pointsBalance}),cheerBtn)),
          el('div',{class:'ma-row',style:'gap:8px;margin-top:8px'},
            el('span',{class:'ma-tag '+(revDueCnt>0?'exploring':'lit'),text:'待温习考点：'+revDueCnt+' 个'})),
          el('div',{class:'ma-prog-track'},el('div',{class:'ma-prog-fill',style:'width:'+pct+'%'})));
        if(st.repairNames&&st.repairNames.length){
          card.appendChild(el('p',{class:'ma-sub',style:'margin-top:8px;color:var(--ma-brand)',text:'待修补考点：'+st.repairNames.join('、')}));
        }

        if(detailsList.length){
          var det=el('details',{style:'margin-top:12px;padding-top:10px;border-top:1px solid #f1e8df'},
            el('summary',{style:'cursor:pointer;font-size:13.5px;font-weight:700;color:var(--ma-ink)',text:'查看全部考点掌握明细（共 '+detailsList.length+' 个考点）'}));
          var detBody=el('div',{style:'margin-top:8px'});
          detailsList.forEach(function(nd){
            var stateCls=nd.needsRepair?'repair':(nd.state||'unexplored');
            var starsTxt=nd.stars>0?(' '+starIcons(nd.stars)):'';
            detBody.appendChild(el('div',{class:'ma-loss-row',style:'flex-wrap:wrap;gap:6px'},
              el('div',{style:'flex:1 1 180px;min-width:160px'},
                el('b',{style:'font-size:13px',text:nd.key+' '+nd.name}),
                nd.domain?el('span',{class:'ma-pill',style:'margin-left:6px',text:nd.domain}):null),
              el('div',{class:'ma-row',style:'gap:6px'},
                el('span',{class:'ma-tag '+stateCls,text:(nd.stateLabel||'未探索')+starsTxt}),
                nd.needsRepair?el('span',{class:'ma-tag repair',text:'待修补'}):null,
                nd.reviewDue?el('span',{class:'ma-tag exploring',text:'需温习'+(nd.daysSincePractice?'（已'+nd.daysSincePractice+'天）':'')}):null)));
          });
          det.appendChild(detBody);
          card.appendChild(det);
        }

        var tBox=el('div',{style:'margin-top:12px;padding-top:10px;border-top:1px solid #f1e8df'},
          el('b',{style:'font-size:13.5px',text:'老师布置的'+subject+'任务'}));
        if(!ch.tasks||!ch.tasks.length){
          tBox.appendChild(el('p',{class:'ma-sub',style:'margin-top:4px',text:'当前没有进行中的老师布置任务。'}));
        }else{
          ch.tasks.forEach(function(tk){
            var done=(tk.status==='done');
            tBox.appendChild(el('div',{class:'ma-loss-row'},
              el('span',{text:tk.targetTitle+'（'+tk.goalLabel+' · 截止 '+tk.dueDate+'）'}),
              el('span',{class:'ma-tag '+(done?'lit':'repair'),text:done?'✓ 已达标':'待完成'})));
          });
        }
        card.appendChild(tBox);
        body.appendChild(card);
      });
    }).catch(function(e){say(e.message,true)});
  }
  loadParent();
}
"""

__all__ = ["ARENA_ROLE_HUB_JS"]
